from dataclasses import dataclass

import pandas as pd
import regex

from datasets.models import Dataset
from datasets.services.ingestion import read_dataframe


MAX_PATTERN_LENGTH = 512
MAX_REPLACEMENT_LENGTH = 512
MAX_CELL_CHARACTERS = 100_000
REGEX_TIMEOUT_SECONDS = 0.05
PREVIEW_CHANGE_LIMIT = 20
SUPPORTED_FLAGS = {
    "IGNORECASE": regex.IGNORECASE,
    "MULTILINE": regex.MULTILINE,
}
NESTED_QUANTIFIER = regex.compile(r"\((?:[^()]|\\.)*[+*](?:[^()]|\\.)*\)[+*{]")


class TransformationValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TransformationSpec:
    pattern: str
    replacement: str
    columns: list[str]
    flags: list[str]


def preview_transformation(dataset: Dataset, spec: TransformationSpec) -> dict:
    compiled = compile_pattern(spec.pattern, spec.flags)
    validate_columns(dataset, spec.columns)
    if len(spec.replacement) > MAX_REPLACEMENT_LENGTH:
        raise TransformationValidationError("Replacement text must be 512 characters or fewer.")
    if compiled.search("") is not None:
        raise TransformationValidationError("Patterns that match empty text are not supported.")

    with dataset.source_file.open("rb") as source:
        frame, _ = read_dataframe(source, dataset.file_format, dataset.sheet_name)

    match_count = 0
    affected_rows: set[int] = set()
    changed_cells = 0
    preview: list[dict] = []

    for row_index, row in frame.reset_index(drop=True).iterrows():
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
                updated = compiled.sub(
                    spec.replacement,
                    text,
                    timeout=REGEX_TIMEOUT_SECONDS,
                )
            except TimeoutError as exc:
                raise TransformationValidationError(
                    "The pattern took too long to evaluate and was stopped."
                ) from exc
            except regex.error as exc:
                raise TransformationValidationError(f"The replacement is invalid: {exc}.") from exc

            match_count += len(matches)
            affected_rows.add(row_index)
            changed_cells += 1
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
    return {
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


def compile_pattern(pattern: str, flags: list[str]) -> regex.Pattern:
    if not pattern:
        raise TransformationValidationError("Enter a regular expression to preview.")
    if len(pattern) > MAX_PATTERN_LENGTH:
        raise TransformationValidationError("Patterns must be 512 characters or fewer.")
    if NESTED_QUANTIFIER.search(pattern):
        raise TransformationValidationError(
            "The pattern contains nested repetition that may be unsafe to execute."
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
