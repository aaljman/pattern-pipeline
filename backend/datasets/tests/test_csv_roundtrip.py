import csv
import shutil
import tempfile
from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase


class CsvRoundTripTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_preserves_lexical_values_in_untouched_columns(self):
        upload = SimpleUploadedFile(
            "identifiers.csv",
            b"sku,notes\n00123,Email ada@example.com\nNA,No email\n",
            content_type="text/csv",
        )
        dataset = self.client.post("/api/datasets/", {"file": upload}, format="multipart")
        payload = {
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
            "replacement": "[REDACTED]",
            "columns": ["notes"],
            "flags": [],
        }

        run = self.client.post(
            f"/api/datasets/{dataset.data['id']}/transforms/apply/",
            payload,
            format="json",
        )
        response = self.client.get(run.data["download_url"])
        rows = list(csv.DictReader(StringIO(b"".join(response.streaming_content).decode())))

        self.assertEqual(run.status_code, 201)
        self.assertEqual([row["sku"] for row in rows], ["00123", "NA"])
