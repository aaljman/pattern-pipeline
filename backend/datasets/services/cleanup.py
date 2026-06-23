from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from datasets.models import Dataset


@dataclass(frozen=True)
class PurgeResult:
    expired_datasets: int
    deleted_files: int


def purge_expired_datasets() -> PurgeResult:
    expired = Dataset.objects.filter(expires_at__lte=timezone.now())
    count = expired.count()
    deleted_files = 0

    for dataset in expired.prefetch_related("transform_runs").iterator(chunk_size=100):
        stored_files = [(dataset.source_file.storage, dataset.source_file.name)]
        stored_files.extend(
            (run.result_file.storage, run.result_file.name)
            for run in dataset.transform_runs.all()
        )

        with transaction.atomic():
            dataset.delete()

        for storage, name in stored_files:
            if name and storage.exists(name):
                storage.delete(name)
                deleted_files += 1

    return PurgeResult(expired_datasets=count, deleted_files=deleted_files)
