import shutil
import tempfile
from datetime import timedelta
from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from datasets.models import Dataset, TransformRun


class PurgeExpiredDatasetsTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_dataset(self, name, expires_at):
        return Dataset.objects.create(
            original_name=name,
            source_file=SimpleUploadedFile(name, b"name\nAda\n"),
            file_format=Dataset.Format.CSV,
            size_bytes=9,
            sha256="0" * 64,
            row_count=1,
            columns=[{"name": "name"}],
            preview=[{"name": "Ada"}],
            expires_at=expires_at,
        )

    def test_dry_run_reports_without_deleting(self):
        expired = self.create_dataset(
            "expired.csv",
            timezone.now() - timedelta(minutes=1),
        )
        output = StringIO()

        call_command("purge_expired_datasets", dry_run=True, stdout=output)

        self.assertIn("1 expired dataset(s)", output.getvalue())
        self.assertTrue(Dataset.objects.filter(id=expired.id).exists())
        self.assertTrue(expired.source_file.storage.exists(expired.source_file.name))

    def test_deletes_expired_records_and_files_only(self):
        expired = self.create_dataset(
            "expired.csv",
            timezone.now() - timedelta(minutes=1),
        )
        active = self.create_dataset(
            "active.csv",
            timezone.now() + timedelta(minutes=30),
        )
        run = TransformRun.objects.create(
            dataset=expired,
            pattern="Ada",
            columns=["name"],
            result_file=SimpleUploadedFile("processed.csv", b"name\nGrace\n"),
            output_format=Dataset.Format.CSV,
        )
        expired_source = expired.source_file.name
        run_result = run.result_file.name
        active_source = active.source_file.name

        call_command("purge_expired_datasets")

        self.assertFalse(Dataset.objects.filter(id=expired.id).exists())
        self.assertFalse(TransformRun.objects.filter(id=run.id).exists())
        self.assertFalse(expired.source_file.storage.exists(expired_source))
        self.assertFalse(run.result_file.storage.exists(run_result))
        self.assertTrue(Dataset.objects.filter(id=active.id).exists())
        self.assertTrue(active.source_file.storage.exists(active_source))
