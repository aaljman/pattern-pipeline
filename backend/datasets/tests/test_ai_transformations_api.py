import json
import os
import shutil
import tempfile
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from google.genai import types as genai_types
from rest_framework.test import APITestCase

from datasets.models import TransformRun
from datasets.services.ai_transformations import (
    ExtractPlan,
    GeminiAiTransformProvider,
    OpenAIAiTransformProvider,
    StandardizePlan,
    TemplateAiTransformProvider,
)
from datasets.services.regex_generation import ProposalGenerationError


class SpyAiTransformProvider:
    name = "spy"
    model = "test-model"

    def __init__(self):
        self.calls = []

    def generate(self, operation, instruction, column):
        self.calls.append(
            {"operation": operation, "instruction": instruction, "column": column}
        )
        if operation == "extract_fields":
            return ExtractPlan(
                pattern=r"^\s*(?P<first_name>[^\s]+)\s+(?P<last_name>.+?)\s*$",
                fields=["first_name", "last_name"],
                explanation="Extracts first and last names.",
                confidence=0.9,
            )
        return StandardizePlan(
            mapping={"new south wales": "NSW"},
            explanation="Standardizes one state name.",
            confidence=0.9,
        )


class FailingAiTransformProvider:
    name = "gemini"
    model = "test-model"

    def generate(self, operation, instruction, column):
        raise ProposalGenerationError("External provider is temporarily unavailable.")


class FakeResponsesClient:
    def __init__(self):
        self.requests = []

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            output_parsed=StandardizePlan(
                mapping={"new south wales": "NSW"},
                explanation="Standardizes state names.",
                confidence=0.9,
            )
        )


class FakeGeminiModels:
    def __init__(self):
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            text=StandardizePlan(
                mapping={"new south wales": "NSW"},
                explanation="Standardizes state names.",
                confidence=0.9,
            ).model_dump_json()
        )


class AiTransformationApiTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        upload = SimpleUploadedFile(
            "customers.csv",
            (
                b"name,state,email\n"
                b"Ada Lovelace,New South Wales,ada@example.com\n"
                b"Lin Chen,N.S.W.,lin@example.com\n"
                b"Grace Hopper,Victoria,grace@example.com\n"
            ),
            content_type="text/csv",
        )
        response = self.client.post("/api/datasets/", {"file": upload}, format="multipart")
        self.dataset_id = response.data["id"]
        self.base_url = f"/api/datasets/{self.dataset_id}/ai-transforms"

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_generates_plan_without_sending_dataset_values(self):
        provider = SpyAiTransformProvider()
        with (
            patch.dict(os.environ, {"AI_PROVIDER": "gemini"}),
            patch(
                "datasets.services.ai_transformations.get_ai_transform_provider",
                return_value=provider,
            ),
        ):
            response = self.client.post(
                f"{self.base_url}/generate/",
                {
                    "operation": "standardize_categories",
                    "instruction": "Use Australian state abbreviations",
                    "column": "state",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data_rows_sent"], 0)
        self.assertEqual(
            provider.calls,
            [
                {
                    "operation": "standardize_categories",
                    "instruction": "Use Australian state abbreviations",
                    "column": "state",
                }
            ],
        )
        self.assertNotIn("New South Wales", str(provider.calls))

    def test_openai_provider_sends_only_instruction_and_column_metadata(self):
        responses = FakeResponsesClient()
        provider = OpenAIAiTransformProvider(
            client=SimpleNamespace(responses=responses),
            model="test-model",
        )

        provider.generate(
            "standardize_categories",
            "Use Australian state abbreviations",
            "state",
        )

        request = responses.requests[0]
        self.assertEqual(request["model"], "test-model")
        self.assertIs(request["text_format"], StandardizePlan)
        self.assertFalse(request["store"])
        self.assertEqual(
            json.loads(request["input"]),
            {
                "operation": "standardize_categories",
                "instruction": "Use Australian state abbreviations",
                "selected_column_name": "state",
            },
        )
        self.assertNotIn("New South Wales", request["input"])

    def test_gemini_provider_sends_only_instruction_and_column_metadata(self):
        models = FakeGeminiModels()
        provider = GeminiAiTransformProvider(
            client=SimpleNamespace(models=models),
            model="gemini-test-model",
        )

        provider.generate(
            "standardize_categories",
            "Use Australian state abbreviations",
            "state",
        )

        request = models.requests[0]
        self.assertEqual(request["model"], "gemini-test-model")
        self.assertEqual(
            json.loads(request["contents"]),
            {
                "operation": "standardize_categories",
                "instruction": "Use Australian state abbreviations",
                "selected_column_name": "state",
            },
        )
        self.assertEqual(request["config"]["response_mime_type"], "application/json")
        self.assertEqual(
            request["config"]["response_json_schema"],
            StandardizePlan.model_json_schema(),
        )
        self.assertEqual(
            request["config"]["thinking_config"].thinking_level,
            genai_types.ThinkingLevel.MINIMAL,
        )
        self.assertNotIn("New South Wales", request["contents"])

    def test_previews_category_standardization_locally(self):
        plan = TemplateAiTransformProvider().generate(
            "standardize_categories",
            "Standardize Australian states",
            "state",
        )
        response = self.client.post(
            f"{self.base_url}/preview/",
            {
                "operation": "standardize_categories",
                "column": "state",
                "parameters": {"mapping": plan.mapping},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["affected_rows"], 3)
        self.assertEqual(response.data["preview"][0]["after"], "NSW")

    def test_auto_uses_external_provider_before_built_in_when_configured(self):
        provider = SpyAiTransformProvider()
        with (
            patch.dict(
                os.environ,
                {
                    "AI_PROVIDER": "auto",
                    "GEMINI_API_KEY": "configured",
                    "OPENAI_API_KEY": "",
                },
            ),
            patch(
                "datasets.services.ai_transformations.get_ai_transform_provider",
                return_value=provider,
            ),
        ):
            response = self.client.post(
                f"{self.base_url}/generate/",
                {
                    "operation": "standardize_categories",
                    "instruction": "Use Australian state abbreviations",
                    "column": "state",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider"], "spy")
        self.assertEqual(
            provider.calls,
            [
                {
                    "operation": "standardize_categories",
                    "instruction": "Use Australian state abbreviations",
                    "column": "state",
                }
            ],
        )

    def test_auto_falls_back_to_simple_built_in_plan_when_external_fails(self):
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "auto",
                "GEMINI_API_KEY": "configured",
                "OPENAI_API_KEY": "",
            },
        ), patch(
            "datasets.services.ai_transformations.get_ai_transform_provider",
            return_value=FailingAiTransformProvider(),
        ):
            response = self.client.post(
                f"{self.base_url}/generate/",
                {
                    "operation": "standardize_categories",
                    "instruction": "Use Australian state abbreviations",
                    "column": "state",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider"], "built-in")
        self.assertEqual(response.data["data_rows_sent"], 0)

    def test_auto_uses_external_provider_for_name_request_on_non_name_column(self):
        provider = SpyAiTransformProvider()
        with (
            patch.dict(
                os.environ,
                {
                    "AI_PROVIDER": "auto",
                    "GEMINI_API_KEY": "configured",
                    "OPENAI_API_KEY": "",
                },
            ),
            patch(
                "datasets.services.ai_transformations.get_ai_transform_provider",
                return_value=provider,
            ),
        ):
            response = self.client.post(
                f"{self.base_url}/generate/",
                {
                    "operation": "extract_fields",
                    "instruction": "Split the names into first and last name",
                    "column": "email",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider"], "spy")
        self.assertEqual(
            provider.calls,
            [
                {
                    "operation": "extract_fields",
                    "instruction": "Split the names into first and last name",
                    "column": "email",
                }
            ],
        )

    def test_auto_does_not_generic_fallback_for_refined_name_request(self):
        with (
            patch.dict(
                os.environ,
                {
                    "AI_PROVIDER": "auto",
                    "GEMINI_API_KEY": "configured",
                    "OPENAI_API_KEY": "",
                },
            ),
            patch(
                "datasets.services.ai_transformations.get_ai_transform_provider",
                return_value=FailingAiTransformProvider(),
            ),
        ):
            response = self.client.post(
                f"{self.base_url}/generate/",
                {
                    "operation": "extract_fields",
                    "instruction": (
                        "Split the names into first and last name and names that are not English"
                    ),
                    "column": "name",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["code"], "generation_failed")
        self.assertIn("External provider", response.data["message"])

    def test_applies_category_standardization_and_exports_result(self):
        response = self.client.post(
            f"{self.base_url}/apply/",
            {
                "operation": "standardize_categories",
                "column": "state",
                "parameters": {
                    "mapping": {
                        "new south wales": "NSW",
                        "n.s.w.": "NSW",
                        "victoria": "VIC",
                    }
                },
                "instruction": "Standardize Australian states",
                "provider": "built-in",
                "model": "optional-transforms-v1",
            },
            format="json",
        )
        downloaded = self.client.get(response.data["download_url"])
        frame = pd.read_csv(BytesIO(b"".join(downloaded.streaming_content)))

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["transform_type"], "standardize_categories")
        self.assertEqual(frame["state"].tolist(), ["NSW", "NSW", "VIC"])

    def test_previews_and_applies_field_extraction(self):
        plan = ExtractPlan(
            pattern=r"^\s*(?P<first_name>[^\s]+)\s+(?P<last_name>.+?)\s*$",
            fields=["first_name", "last_name"],
            explanation="Extracts first and last names.",
            confidence=0.9,
        )
        payload = {
            "operation": "extract_fields",
            "column": "name",
            "parameters": {
                "pattern": plan.pattern,
                "flags": plan.flags,
                "fields": plan.fields,
            },
        }

        preview = self.client.post(f"{self.base_url}/preview/", payload, format="json")
        applied = self.client.post(f"{self.base_url}/apply/", payload, format="json")
        downloaded = self.client.get(applied.data["download_url"])
        frame = pd.read_csv(BytesIO(b"".join(downloaded.streaming_content)))

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.data["output_columns"], ["first_name", "last_name"])
        self.assertEqual(preview.data["preview"][0]["extracted"]["first_name"], "Ada")
        self.assertEqual(applied.status_code, 201)
        self.assertEqual(applied.data["transform_type"], "extract_fields")
        self.assertEqual(frame["last_name"].tolist(), ["Lovelace", "Chen", "Hopper"])
        self.assertEqual(TransformRun.objects.count(), 1)

    def test_rejects_extraction_fields_that_do_not_match_named_groups(self):
        response = self.client.post(
            f"{self.base_url}/preview/",
            {
                "operation": "extract_fields",
                "column": "name",
                "parameters": {
                    "pattern": r"(?P<first_name>\w+)",
                    "flags": [],
                    "fields": ["different_name"],
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("named capture groups", response.data["message"])

    def test_rejects_conflicting_normalized_category_mappings(self):
        response = self.client.post(
            f"{self.base_url}/preview/",
            {
                "operation": "standardize_categories",
                "column": "state",
                "parameters": {
                    "mapping": {
                        "NSW": "New South Wales",
                        "nsw": "NSW",
                    }
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("conflicting values", response.data["message"])
