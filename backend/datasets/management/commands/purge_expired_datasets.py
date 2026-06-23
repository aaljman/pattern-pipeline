from django.core.management.base import BaseCommand
from django.utils import timezone

from datasets.models import Dataset
from datasets.services.cleanup import purge_expired_datasets


class Command(BaseCommand):
    help = "Delete expired datasets, transformation runs, and their stored files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many datasets are expired without deleting them.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            count = Dataset.objects.filter(expires_at__lte=timezone.now()).count()
            self.stdout.write(f"{count} expired dataset(s) would be deleted.")
            return

        result = purge_expired_datasets()
        self.stdout.write(
            self.style.SUCCESS(
                "Deleted "
                f"{result.expired_datasets} expired dataset(s) and "
                f"{result.deleted_files} stored file(s)."
            )
        )
