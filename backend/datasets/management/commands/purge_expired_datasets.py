from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from datasets.models import Dataset


class Command(BaseCommand):
    help = "Delete expired datasets, transformation runs, and their stored files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many datasets are expired without deleting them.",
        )

    def handle(self, *args, **options):
        expired = Dataset.objects.filter(expires_at__lte=timezone.now())
        count = expired.count()

        if options["dry_run"]:
            self.stdout.write(f"{count} expired dataset(s) would be deleted.")
            return

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

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {count} expired dataset(s) and {deleted_files} stored file(s)."
            )
        )
