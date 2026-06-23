import json
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from google.genai import types as genai_types
from rest_framework.test import APITestCase

from datasets.services.regex_generation import (
    GeminiRegexProvider,
    OpenAIRegexProvider,
    RegexProposal,
    TemplateRegexProvider,
)


class SpyRegexProvider:
    name = "spy"
    model = "test-model"

    def __init__(self):
        self.calls = []

    def generate(self, instruction, column_names):
        self.calls.append({"instruction": instruction, "column_names": column_names})
        return RegexProposal(
            pattern=r"\b[A-Z]{3}\b",
            explanation="Matches a three-letter uppercase code.",
            positive_examples=["ABC"],
            negative_examples=["Abc"],
            confidence=0.9,
        )


class FakeResponsesClient:
    def __init__(self):
        self.requests = []

    def parse(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            output_parsed=RegexProposal(
                pattern=r"\b[A-Z]{3}\b",
                explanation="Matches a three-letter uppercase code.",
                confidence=0.9,
            )
        )


class FakeGeminiModels:
    def __init__(self):
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            text=RegexProposal(
                pattern=r"\b[A-Z]{3}\b",
                explanation="Matches a three-letter uppercase code.",
                confidence=0.9,
            ).model_dump_json()
        )


class RegexGenerationApiTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        upload = SimpleUploadedFile(
            "customers.csv",
            b"name,email,score\nAda,ada@example.com,10\n",
            content_type="text/csv",
        )
        response = self.client.post("/api/datasets/", {"file": upload}, format="multipart")
        self.url = f"/api/datasets/{response.data['id']}/transforms/generate/"

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_generates_structured_proposal_without_dataset_rows(self):
        provider = SpyRegexProvider()
        with patch(
            "datasets.services.regex_generation.get_regex_provider",
            return_value=provider,
        ):
            response = self.client.post(
                self.url,
                {"instruction": "Find customer codes", "columns": ["name"]},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["pattern"], r"\b[A-Z]{3}\b")
        self.assertEqual(response.data["data_rows_sent"], 0)
        self.assertEqual(
            provider.calls,
            [{"instruction": "Find customer codes", "column_names": ["name"]}],
        )
        self.assertNotIn("Ada", str(provider.calls))
        self.assertNotIn("ada@example.com", str(provider.calls))

    def test_openai_provider_sends_only_instruction_and_column_metadata(self):
        responses = FakeResponsesClient()
        client = SimpleNamespace(responses=responses)
        provider = OpenAIRegexProvider(client=client, model="test-model")

        provider.generate("Find customer codes", ["name"])

        request = responses.requests[0]
        self.assertEqual(request["model"], "test-model")
        self.assertIs(request["text_format"], RegexProposal)
        self.assertFalse(request["store"])
        self.assertEqual(
            json.loads(request["input"]),
            {
                "instruction": "Find customer codes",
                "selected_column_names": ["name"],
                "allowed_flags": ["IGNORECASE", "MULTILINE"],
            },
        )
        self.assertNotIn("Ada", request["input"])
        self.assertNotIn("ada@example.com", request["input"])

    def test_gemini_provider_sends_only_instruction_and_column_metadata(self):
        models = FakeGeminiModels()
        provider = GeminiRegexProvider(
            client=SimpleNamespace(models=models),
            model="gemini-test-model",
        )

        provider.generate("Find customer codes", ["name"])

        request = models.requests[0]
        self.assertEqual(request["model"], "gemini-test-model")
        self.assertEqual(
            json.loads(request["contents"]),
            {
                "instruction": "Find customer codes",
                "selected_column_names": ["name"],
                "allowed_flags": ["IGNORECASE", "MULTILINE"],
            },
        )
        self.assertEqual(request["config"]["response_mime_type"], "application/json")
        self.assertEqual(
            request["config"]["response_json_schema"],
            RegexProposal.model_json_schema(),
        )
        self.assertEqual(
            request["config"]["thinking_config"].thinking_level,
            genai_types.ThinkingLevel.MINIMAL,
        )
        self.assertNotIn("Ada", request["contents"])
        self.assertNotIn("ada@example.com", request["contents"])

    def test_uses_built_in_email_fallback(self):
        with patch(
            "datasets.services.regex_generation.get_regex_provider",
            return_value=TemplateRegexProvider(),
        ):
            response = self.client.post(
                self.url,
                {"instruction": "Find email addresses", "columns": ["email"]},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider"], "built-in")
        self.assertIn("@", response.data["positive_examples"][0])

    def test_rejects_non_text_column_before_provider_call(self):
        provider = SpyRegexProvider()
        with patch(
            "datasets.services.regex_generation.get_regex_provider",
            return_value=provider,
        ):
            response = self.client.post(
                self.url,
                {"instruction": "Find numbers", "columns": ["score"]},
                format="json",
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(provider.calls, [])

    def test_rejects_unsafe_provider_output(self):
        provider = SpyRegexProvider()
        provider.generate = lambda instruction, columns: RegexProposal(
            pattern="(a+)+$",
            explanation="Unsafe nested repetition.",
            confidence=0.1,
        )
        with patch(
            "datasets.services.regex_generation.get_regex_provider",
            return_value=provider,
        ):
            response = self.client.post(
                self.url,
                {"instruction": "Find repeated a", "columns": ["name"]},
                format="json",
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("safety gate", response.data["message"])

    def test_rejects_examples_that_contradict_provider_pattern(self):
        provider = SpyRegexProvider()
        provider.generate = lambda instruction, columns: RegexProposal(
            pattern=r"\d+",
            explanation="Claims to match letters.",
            positive_examples=["ABC"],
            negative_examples=["123"],
            confidence=0.9,
        )
        with patch(
            "datasets.services.regex_generation.get_regex_provider",
            return_value=provider,
        ):
            response = self.client.post(
                self.url,
                {"instruction": "Find codes", "columns": ["name"]},
                format="json",
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("examples contradict", response.data["message"])

    def test_built_in_routing_rejects_substrings_and_ambiguous_intents(self):
        provider = TemplateRegexProvider()

        with patch(
            "datasets.services.regex_generation.get_regex_provider",
            return_value=provider,
        ):
            substring = self.client.post(
                self.url,
                {"instruction": "Find microphone IDs", "columns": ["name"]},
                format="json",
            )
            ambiguous = self.client.post(
                self.url,
                {"instruction": "Find URLs in email bodies", "columns": ["name"]},
                format="json",
            )

        self.assertEqual(substring.status_code, 422)
        self.assertEqual(ambiguous.status_code, 422)
        self.assertIn("multiple", ambiguous.data["message"])
