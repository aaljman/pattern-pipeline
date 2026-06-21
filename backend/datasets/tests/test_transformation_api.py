import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APITestCase


class TransformationPreviewApiTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        upload = SimpleUploadedFile(
            "customers.csv",
            (
                b"name,email,notes,score\n"
                b"Ada,ada@example.com,Email ada@example.com,10\n"
                b"Lin,lin@example.com,No address here,20\n"
            ),
            content_type="text/csv",
        )
        response = self.client.post("/api/datasets/", {"file": upload}, format="multipart")
        self.dataset_id = response.data["id"]
        self.url = f"/api/datasets/{self.dataset_id}/transforms/preview/"

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_previews_changes_in_selected_columns_only(self):
        response = self.client.post(
            self.url,
            {
                "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                "replacement": "[REDACTED]",
                "columns": ["notes"],
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["match_count"], 1)
        self.assertEqual(response.data["affected_rows"], 1)
        self.assertEqual(response.data["changed_cells"], 1)
        self.assertEqual(
            response.data["preview"][0]["changes"][0]["after"],
            "Email [REDACTED]",
        )

    def test_applies_supported_flags(self):
        response = self.client.post(
            self.url,
            {
                "pattern": "email",
                "replacement": "Contact",
                "columns": ["notes"],
                "flags": ["IGNORECASE"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["match_count"], 1)

    def test_rejects_non_text_columns(self):
        response = self.client.post(
            self.url,
            {
                "pattern": r"\d+",
                "replacement": "0",
                "columns": ["score"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "unsafe_transform")
        self.assertIn("Only text columns", response.data["message"])

    def test_rejects_nested_quantifiers(self):
        response = self.client.post(
            self.url,
            {
                "pattern": "(a+)+$",
                "replacement": "",
                "columns": ["notes"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nested repetition", response.data["message"])

    def test_rejects_patterns_that_match_empty_text(self):
        response = self.client.post(
            self.url,
            {
                "pattern": "^",
                "replacement": "prefix",
                "columns": ["notes"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("match empty text", response.data["message"])

    def test_rejects_recursive_patterns(self):
        response = self.client.post(
            self.url,
            {
                "pattern": "(?R)",
                "replacement": "x",
                "columns": ["notes"],
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Recursive", response.data["message"])

    def test_rejects_zero_width_matches_in_cell_values(self):
        response = self.client.post(
            self.url,
            {
                "pattern": "(?=Email)",
                "replacement": "x",
                "columns": ["notes"],
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("zero-width", response.data["message"])

    def test_returns_warning_when_no_matches_are_found(self):
        response = self.client.post(
            self.url,
            {
                "pattern": "never-matches",
                "replacement": "x",
                "columns": ["notes"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["match_count"], 0)
        self.assertEqual(len(response.data["warnings"]), 1)
