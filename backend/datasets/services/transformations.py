from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from time import monotonic

import pandas as pd
import regex
from django.core.files.base import ContentFile
from django.db import transaction

from datasets.models import Dataset, TransformRun
from datasets.services.ingestion import PREVIEW_ROWS, read_dataframe, serialise_preview


MAX_PATTERN_LENGTH = 512
MAX_REPLACEMENT_LENGTH = 512
MAX_CELL_CHARACTERS = 100_000
MAX_OUTPUT_CELL_CHARACTERS = 200_000
MAX_TRANSFORM_CELLS = 200_000
MAX_TOTAL_MATCHES = 100_000
MAX_OUTPUT_BYTES = 25 * 1024 * 1024
MAX_TRANSFORM_SECONDS = 10
REGEX_TIMEOUT_SECONDS = 0.05
PREVIEW_CHANGE_LIMIT = 20
SUPPORTED_FLAGS = {
    "IGNORECASE": regex.IGNORECASE,
    "MULTILINE": regex.MULTILINE,
}
NESTED_QUANTIFIER = regex.compile(r"\((?:[^()]|\\.)*[+*](?:[^()]|\\.)*\)[+*{]")
RECURSIVE_PATTERN = regex.compile(
    r"\(\?(?:R|0|[1-9]\d*|&[A-Za-z_]\w*|P>[A-Za-z_]\w*)\)"
)


class TransformationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TransformationSpec:
    pattern: str
    replacement: str
    columns: list[str]
    flags: list[str]


def preview_transformation(dataset: Dataset, spec: TransformationSpec) -> dict:
    _, result = execute_transformation(dataset, spec)
    return result


def execute_transformation(
    dataset: Dataset,
    spec: TransformationSpec,
) -> tuple[pd.DataFrame, dict]:
    compiled = compile_pattern(spec.pattern, spec.flags)
    validate_columns(dataset, spec.columns)
    if len(spec.replacement) > MAX_REPLACEMENT_LENGTH:
        raise TransformationValidationError("Replacement text must be 512 characters or fewer.")
    try:
        if compiled.search("", timeout=REGEX_TIMEOUT_SECONDS) is not None:
            raise TransformationValidationError("Patterns that match empty text are not supported.")
    except (MemoryError, TimeoutError) as exc:
        raise TransformationValidationError(
            "The pattern could not be validated within the safety limits."
        ) from exc

    with dataset.source_file.open("rb") as source:
        frame, _ = read_dataframe(source, dataset.file_format, dataset.sheet_name)
    frame = frame.reset_index(drop=True)
    if len(frame.index) * len(spec.columns) > MAX_TRANSFORM_CELLS:
        raise TransformationValidationError(
            f"A transformation may inspect at most {MAX_TRANSFORM_CELLS:,} cells."
        )
    transformed = frame.copy()
    started_at = monotonic()

    match_count = 0
    affected_rows: set[int] = set()
    changed_cells = 0
    preview: list[dict] = []

    for row_index, row in frame.iterrows():
        if monotonic() - started_at > MAX_TRANSFORM_SECONDS:
            raise TransformationValidationError(
                "The transformation exceeded the 10 second execution limit."
            )
        row_changes = []
        for column in spec.columns:
            value = row[column]
            if pd.isna(value):
                continue
            text = str(value)
            if len(text) > MAX_CELL_CHARACTERS:
                raise TransformationValidationError(
                    f"Cell {row_index + 1} in {column} exceeds the 100,000 character safety limit."
                )
            try:
                matches = list(compiled.finditer(text, timeout=REGEX_TIMEOUT_SECONDS))
                if not matches:
                    continue
                if any(match.start() == match.end() for match in matches):
                    raise TransformationValidationError(
                        "Patterns that produce zero-width matches are not supported."
                    )
                if match_count + len(matches) > MAX_TOTAL_MATCHES:
                    raise TransformationValidationError(
                        f"A transformation may produce at most {MAX_TOTAL_MATCHES:,} matches."
                    )
                updated = compiled.sub(
                    spec.replacement,
                    text,
                    timeout=REGEX_TIMEOUT_SECONDS,
                )
                if len(updated) > MAX_OUTPUT_CELL_CHARACTERS:
                    raise TransformationValidationError(
                        "A transformed cell may contain at most 200,000 characters."
                    )
            except (MemoryError, TimeoutError) as exc:
                raise TransformationValidationError(
                    "The pattern took too long to evaluate and was stopped."
                ) from exc
            except regex.error as exc:
                raise TransformationValidationError(f"The replacement is invalid: {exc}.") from exc

            match_count += len(matches)
            if updated == text:
                continue
            affected_rows.add(row_index)
            changed_cells += 1
            transformed.at[row_index, column] = updated
            if len(preview) < PREVIEW_CHANGE_LIMIT:
                row_changes.append(
                    {
                        "column": column,
                        "before": text,
                        "after": updated,
                        "matches": [
                            {
                                "start": match.start(),
                                "end": match.end(),
                                "text": match.group(0),
                            }
                            for match in matches
                        ],
                    }
                )

        if row_changes and len(preview) < PREVIEW_CHANGE_LIMIT:
            preview.append({"row_index": row_index, "changes": row_changes})

    warnings = build_warnings(len(frame.index), len(affected_rows), match_count)
    return transformed, {
        "pattern": spec.pattern,
        "replacement": spec.replacement,
        "columns": spec.columns,
        "flags": spec.flags,
        "match_count": match_count,
        "affected_rows": len(affected_rows),
        "changed_cells": changed_cells,
        "total_rows": len(frame.index),
        "warnings": warnings,
        "preview": preview,
    }


def apply_transformation(
    dataset: Dataset,
    spec: TransformationSpec,
    metadata: dict | None = None,
) -> TransformRun:
    transformed, result = execute_transformation(dataset, spec)
    return persist_transformation_run(
        dataset=dataset,
        transformed=transformed,
        result=result,
        transform_type=TransformRun.Type.REGEX_REPLACE,
        parameters={},
        pattern=spec.pattern,
        flags=spec.flags,
        replacement=spec.replacement,
        columns=spec.columns,
        metadata=metadata,
    )


def persist_transformation_run(
    *,
    dataset: Dataset,
    transformed: pd.DataFrame,
    result: dict,
    transform_type: str,
    parameters: dict,
    pattern: str,
    flags: list[str],
    replacement: str,
    columns: list[str],
    metadata: dict | None = None,
) -> TransformRun:
    safe_frame, escaped_formulas = escape_spreadsheet_formulas(transformed)
    warnings = list(result["warnings"])
    if escaped_formulas:
        warnings.append(
            f"Escaped {escaped_formulas} formula-like cell value(s) for safe spreadsheet export."
        )

    output_format = dataset.file_format
    content = serialise_output(safe_frame, output_format, dataset.sheet_name)
    if len(content) > MAX_OUTPUT_BYTES:
        raise TransformationValidationError("The processed file exceeds the 25 MB output limit.")
    run = TransformRun(
        dataset=dataset,
        transform_type=transform_type,
        parameters=parameters,
        instruction=(metadata or {}).get("instruction", ""),
        pattern=pattern,
        flags=flags,
        replacement=replacement,
        columns=columns,
        explanation=(metadata or {}).get("explanation", ""),
        provider=(metadata or {}).get("provider", ""),
        model_name=(metadata or {}).get("model", ""),
        match_count=result["match_count"],
        affected_rows=result["affected_rows"],
        changed_cells=result["changed_cells"],
        warnings=warnings,
        result_columns=[str(column) for column in safe_frame.columns],
        result_preview=serialise_preview(safe_frame.head(PREVIEW_ROWS)),
        output_format=output_format,
    )
    filename = f"processed-{Path(dataset.original_name).stem}.{output_format}"
    try:
        with transaction.atomic():
            run.result_file.save(filename, ContentFile(content), save=False)
            run.save()
    except Exception:
        run.result_file.delete(save=False)
        raise
    return run


def escape_spreadsheet_formulas(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    safe_frame = frame.copy()
    escaped = 0
    for column in safe_frame.columns:
        for row_index, value in safe_frame[column].items():
            if isinstance(value, str) and value.lstrip(" \t\r\n\v\f").startswith(
                ("=", "+", "-", "@")
            ):
                safe_frame.at[row_index, column] = f"'{value}"
                escaped += 1
    return safe_frame, escaped


def serialise_output(frame: pd.DataFrame, output_format: str, sheet_name: str) -> bytes:
    if output_format == Dataset.Format.CSV:
        output = StringIO(newline="")
        frame.to_csv(output, index=False, lineterminator="\n")
        return output.getvalue().encode("utf-8")

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=(sheet_name or "Processed")[:31])
    return output.getvalue()


def compile_pattern(pattern: str, flags: list[str]) -> regex.Pattern:
    if not pattern:
        raise TransformationValidationError("Enter a regular expression to preview.")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise TransformationValidationError("Patterns must be 512 characters or fewer.")
    if NESTED_QUANTIFIER.search(pattern):
        raise TransformationValidationError(
            "The pattern contains nested repetition that may be unsafe to execute."
        )
    if RECURSIVE_PATTERN.search(pattern):
        raise TransformationValidationError(
            "Recursive and subroutine regex patterns are not supported."
        )

    combined_flags = 0
    for flag in flags:
        if flag not in SUPPORTED_FLAGS:
            raise TransformationValidationError(f"Unsupported regex flag: {flag}.")
        combined_flags |= SUPPORTED_FLAGS[flag]

    try:
        return regex.compile(pattern, combined_flags)
    except regex.error as exc:
        raise TransformationValidationError(f"The regular expression is invalid: {exc}.") from exc


def validate_columns(dataset: Dataset, selected_columns: list[str]) -> None:
    if not selected_columns:
        raise TransformationValidationError("Select at least one text column.")
    text_columns = {
        column["name"] for column in dataset.columns if column["type"] == "text"
    }
    invalid_columns = set(selected_columns) - text_columns
    if invalid_columns:
        names = ", ".join(sorted(invalid_columns))
        raise TransformationValidationError(f"Only text columns can be transformed: {names}.")


def build_warnings(total_rows: int, affected_rows: int, match_count: int) -> list[str]:
    warnings = []
    if match_count == 0:
        warnings.append("No matches were found in the selected columns.")
    if total_rows and affected_rows / total_rows > 0.8:
        warnings.append("This pattern changes more than 80% of rows. Review it carefully.")
    return warnings
