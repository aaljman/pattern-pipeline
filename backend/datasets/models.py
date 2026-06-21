import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


def default_expiry():
    return timezone.now() + timedelta(hours=1)


def dataset_upload_path(instance, filename: str) -> str:
    return f"datasets/{instance.id}/{filename}"


def transform_upload_path(instance, filename: str) -> str:
    return f"transforms/{instance.id}/{filename}"


class StoredFile(models.Model):
    name = models.CharField(max_length=500, primary_key=True)
    content = models.BinaryField()
    size_bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class Dataset(models.Model):
    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        XLSX = "xlsx", "Excel"

    class Status(models.TextChoices):
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_name = models.CharField(max_length=255)
    source_file = models.FileField(upload_to=dataset_upload_path)
    file_format = models.CharField(max_length=8, choices=Format.choices)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    sheet_name = models.CharField(max_length=255, blank=True)
    row_count = models.PositiveBigIntegerField()
    columns = models.JSONField(default=list)
    preview = models.JSONField(default=list)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.READY,
    )
    expires_at = models.DateTimeField(default=default_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TransformRun(models.Model):
    class Type(models.TextChoices):
        REGEX_REPLACE = "regex_replace", "Regex replace"
        STANDARDIZE_CATEGORIES = "standardize_categories", "Standardize categories"
        EXTRACT_FIELDS = "extract_fields", "Extract fields"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="transform_runs")
    transform_type = models.CharField(
        max_length=32,
        choices=Type.choices,
        default=Type.REGEX_REPLACE,
    )
    parameters = models.JSONField(default=dict)
    instruction = models.TextField(blank=True)
    pattern = models.TextField()
    flags = models.JSONField(default=list)
    replacement = models.TextField(blank=True)
    columns = models.JSONField(default=list)
    explanation = models.TextField(blank=True)
    provider = models.CharField(max_length=64, blank=True)
    model_name = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    match_count = models.PositiveBigIntegerField(default=0)
    affected_rows = models.PositiveBigIntegerField(default=0)
    changed_cells = models.PositiveBigIntegerField(default=0)
    warnings = models.JSONField(default=list)
    result_columns = models.JSONField(default=list)
    result_preview = models.JSONField(default=list)
    result_file = models.FileField(upload_to=transform_upload_path)
    output_format = models.CharField(max_length=8, choices=Dataset.Format.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
