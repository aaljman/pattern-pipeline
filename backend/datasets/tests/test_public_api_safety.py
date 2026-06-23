import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

from datasets.models import Dataset, TransformRun
from datasets.views import PURGE_CACHE_KEY


class PublicApiSafetyTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()

    def tearDown(self):
        cache.clear()
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def upload(self, name="customers.csv"):
        file = SimpleUploadedFile(
            name,
            b"name,notes\nAda,Email ada@example.com\n",
            content_type="text/csv",
        )
        return self.client.post("/api/datasets/", {"file": file}, format="multipart")

    def test_private_responses_disable_caching(self):
        created = self.upload()

        response = self.client.get(f"/api/datasets/{created.data['id']}/")

        self.assertEqual(response.headers["Cache-Control"], "no-store, private")

    def test_returns_gone_for_expired_dataset(self):
        created = self.upload()
        Dataset.objects.filter(id=created.data["id"]).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        response = self.client.get(f"/api/datasets/{created.data['id']}/")

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.data["code"], "dataset_expired")

    def test_returns_gone_when_output_artifact_is_missing(self):
        created = self.upload()
        payload = {
            "pattern": "Email",
            "replacement": "Contact",
            "columns": ["notes"],
            "flags": [],
        }
        run_response = self.client.post(
            f"/api/datasets/{created.data['id']}/transforms/apply/",
            payload,
            format="json",
        )
        run = TransformRun.objects.get(id=run_response.data["id"])
        run.result_file.delete(save=False)

        response = self.client.get(run_response.data["download_url"])

        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.data["code"], "artifact_unavailable")

    def test_throttles_repeated_anonymous_uploads(self):
        with patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"upload": "1/minute"}):
            first = self.upload("first.csv")
            second = self.upload("second.csv")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 429)

    def test_upload_opportunistically_purges_expired_artifacts(self):
        expired = self.upload("expired.csv")
        dataset = Dataset.objects.get(id=expired.data["id"])
        source_name = dataset.source_file.name
        Dataset.objects.filter(id=dataset.id).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        cache.delete(PURGE_CACHE_KEY)

        fresh = self.upload("fresh.csv")

        self.assertEqual(fresh.status_code, 201)
        self.assertFalse(Dataset.objects.filter(id=dataset.id).exists())
        self.assertFalse(dataset.source_file.storage.exists(source_name))
