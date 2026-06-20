import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


def default_expiry():
    return timezone.now() + timedelta(hours=1)


def dataset_upload_path(instance, filename: str) -> str:
    return f"datasets/{instance.id}/{filename}"


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
