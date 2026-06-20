import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from django.core.files.uploadedfile import UploadedFile
from pandas.api import types as pandas_types

from datasets.models import Dataset


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
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
    except (OSError, UnicodeError, ValueError, pd.errors.ParserError) as exc:
        raise DatasetValidationError(
            "The file could not be parsed. Check that it is a valid CSV or XLSX file."
        ) from exc

    upload.seek(0)
    return Dataset.objects.create(
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

    return ALLOWED_EXTENSIONS[suffix]


def hash_file(upload: UploadedFile) -> str:
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest()


def parse_dataset(upload: BinaryIO, file_format: str) -> ParsedDataset:
    if file_format == Dataset.Format.CSV:
        frame = pd.read_csv(upload)
        sheet_name = ""
    else:
        workbook = pd.ExcelFile(upload, engine="openpyxl")
        sheet_name = workbook.sheet_names[0]
        frame = workbook.parse(sheet_name)

    if not len(frame.columns):
        raise DatasetValidationError("The file does not contain any columns.")

    columns = [profile_column(frame, str(name)) for name in frame.columns]
    return ParsedDataset(
        file_format=file_format,
        sheet_name=sheet_name,
        row_count=len(frame.index),
        columns=columns,
        preview=serialise_preview(frame.head(PREVIEW_ROWS)),
    )


def profile_column(frame: pd.DataFrame, name: str) -> dict:
    series = frame[name]
    if pandas_types.is_bool_dtype(series.dtype):
        data_type = "boolean"
    elif pandas_types.is_numeric_dtype(series.dtype):
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
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value
