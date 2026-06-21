import hashlib
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from openpyxl.utils.exceptions import InvalidFileException
from pandas.api import types as pandas_types

from datasets.models import Dataset


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_XLSX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_XLSX_ARCHIVE_ENTRIES = 10_000
MAX_ROWS = 100_000
MAX_COLUMNS = 200
MAX_CELLS = 2_000_000
PREVIEW_ROWS = 20
ALLOWED_EXTENSIONS = {".csv": Dataset.Format.CSV, ".xlsx": Dataset.Format.XLSX}


class DatasetValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedDataset:
    file_format: str
    sheet_name: str
    row_count: int
    columns: list[dict]
    preview: list[dict]


def ingest_dataset(upload: UploadedFile) -> Dataset:
    file_format = validate_upload(upload)
    digest = hash_file(upload)

    try:
        parsed = parse_dataset(upload, file_format)
    except DatasetValidationError:
        raise
    except (
        InvalidFileException,
        OSError,
        TypeError,
        UnicodeError,
        ValueError,
        pd.errors.ParserError,
        zipfile.BadZipFile,
    ) as exc:
        raise DatasetValidationError(
            "The file could not be parsed. Check that it is a valid CSV or XLSX file."
        ) from exc

    upload.seek(0)
    dataset = Dataset(
        original_name=Path(upload.name).name,
        source_file=upload,
        file_format=parsed.file_format,
        size_bytes=upload.size,
        sha256=digest,
        sheet_name=parsed.sheet_name,
        row_count=parsed.row_count,
        columns=parsed.columns,
        preview=parsed.preview,
    )
    try:
        with transaction.atomic():
            dataset.save()
    except Exception:
        dataset.source_file.delete(save=False)
        raise
    return dataset


def validate_upload(upload: UploadedFile) -> str:
    suffix = Path(upload.name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise DatasetValidationError("Only CSV and XLSX files are supported.")
    if upload.size == 0:
        raise DatasetValidationError("The uploaded file is empty.")
    if upload.size > MAX_UPLOAD_BYTES:
        raise DatasetValidationError("Files must be 20 MB or smaller.")

    if suffix == ".xlsx":
        signature = upload.read(4)
        upload.seek(0)
        if signature != b"PK\x03\x04":
            raise DatasetValidationError("The XLSX file signature is invalid.")
        validate_xlsx_archive(upload)

    return ALLOWED_EXTENSIONS[suffix]


def validate_xlsx_archive(upload: UploadedFile) -> None:
    try:
        with zipfile.ZipFile(upload) as archive:
            entries = archive.infolist()
            expanded_bytes = sum(entry.file_size for entry in entries)
    except (OSError, zipfile.BadZipFile) as exc:
        upload.seek(0)
        raise DatasetValidationError("The XLSX file is not a valid workbook archive.") from exc
    finally:
        upload.seek(0)

    if len(entries) > MAX_XLSX_ARCHIVE_ENTRIES:
        raise DatasetValidationError("The XLSX workbook contains too many archive entries.")
    if expanded_bytes > MAX_XLSX_UNCOMPRESSED_BYTES:
        raise DatasetValidationError("The expanded XLSX workbook must be 100 MB or smaller.")


def hash_file(upload: UploadedFile) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def parse_dataset(upload: BinaryIO, file_format: str) -> ParsedDataset:
    frame, sheet_name = read_dataframe(upload, file_format)

    if not len(frame.columns):
        raise DatasetValidationError("The file does not contain any columns.")
    if len(frame.index) > MAX_ROWS:
        raise DatasetValidationError(f"Files may contain at most {MAX_ROWS:,} rows.")
    if len(frame.columns) > MAX_COLUMNS:
        raise DatasetValidationError(f"Files may contain at most {MAX_COLUMNS:,} columns.")
    if len(frame.index) * len(frame.columns) > MAX_CELLS:
        raise DatasetValidationError(f"Files may contain at most {MAX_CELLS:,} cells.")

    columns = [profile_column(frame, name) for name in frame.columns]
    return ParsedDataset(
        file_format=file_format,
        sheet_name=sheet_name,
        row_count=len(frame.index),
        columns=columns,
        preview=serialise_preview(frame.head(PREVIEW_ROWS)),
    )


def read_dataframe(
    source: BinaryIO,
    file_format: str,
    sheet_name: str = "",
) -> tuple[pd.DataFrame, str]:
    if file_format == Dataset.Format.CSV:
        frame = pd.read_csv(
            source,
            dtype=str,
            keep_default_na=False,
            nrows=MAX_ROWS + 1,
        ).replace("", pd.NA)
        sheet = ""
    else:
        workbook = pd.ExcelFile(source, engine="openpyxl")
        sheet = sheet_name or workbook.sheet_names[0]
        frame = workbook.parse(sheet, nrows=MAX_ROWS + 1)

    frame.columns = normalize_column_names(frame.columns)
    return frame, sheet


def normalize_column_names(columns) -> list[str]:
    names = []
    counts: dict[str, int] = {}
    for value in columns:
        base = str(value)
        counts[base] = counts.get(base, 0) + 1
        names.append(base if counts[base] == 1 else f"{base}.{counts[base] - 1}")
    return names


def profile_column(frame: pd.DataFrame, name: str) -> dict:
    series = frame[name]
    present = series.dropna()
    normalized = present.astype(str).str.strip()
    lowered = normalized.str.casefold()

    if pandas_types.is_bool_dtype(series.dtype) or (
        len(present) and lowered.isin({"true", "false"}).all()
    ):
        data_type = "boolean"
    elif pandas_types.is_numeric_dtype(series.dtype) or (
        len(present) and pd.to_numeric(normalized, errors="coerce").notna().all()
    ):
        data_type = "number"
    elif pandas_types.is_datetime64_any_dtype(series.dtype):
        data_type = "datetime"
    else:
        data_type = "text"

    return {
        "name": name,
        "type": data_type,
        "missing_count": int(series.isna().sum()),
    }


def serialise_preview(frame: pd.DataFrame) -> list[dict]:
    safe_frame = frame.astype(object).where(pd.notna(frame), None)
    records = safe_frame.to_dict(orient="records")
    return [{str(key): json_value(value) for key, value in row.items()} for row in records]


def json_value(value):
    if isinstance(value, (pd.Timestamp, datetime, date, time)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value
