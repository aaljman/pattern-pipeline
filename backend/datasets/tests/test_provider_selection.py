import os
from unittest.mock import patch

from django.test import SimpleTestCase

from datasets.services.provider_selection import (
    DEFAULT_GEMINI_TIMEOUT_MS,
    ProviderConfigurationError,
    get_gemini_timeout_ms,
    select_provider_name,
)


class ProviderSelectionTests(SimpleTestCase):
    def test_auto_prefers_gemini_when_both_keys_exist(self):
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "auto",
                "GEMINI_API_KEY": "gemini-key",
                "OPENAI_API_KEY": "openai-key",
            },
            clear=True,
        ):
            self.assertEqual(select_provider_name(), "gemini")

    def test_auto_uses_openai_when_only_its_key_exists(self):
        with patch.dict(
            os.environ,
            {"AI_PROVIDER": "auto", "OPENAI_API_KEY": "openai-key"},
            clear=True,
        ):
            self.assertEqual(select_provider_name(), "openai")

    def test_auto_uses_built_in_provider_without_keys(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "auto"}, clear=True):
            self.assertEqual(select_provider_name(), "built-in")

    def test_auto_ignores_blank_keys(self):
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "auto",
                "GEMINI_API_KEY": "   ",
                "OPENAI_API_KEY": "",
            },
            clear=True,
        ):
            self.assertEqual(select_provider_name(), "built-in")

    def test_explicit_provider_requires_its_key(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=True):
            with self.assertRaisesMessage(
                ProviderConfigurationError,
                "GEMINI_API_KEY is not configured",
            ):
                select_provider_name()

    def test_explicit_built_in_ignores_api_keys(self):
        with patch.dict(
            os.environ,
            {
                "AI_PROVIDER": "built-in",
                "GEMINI_API_KEY": "gemini-key",
                "OPENAI_API_KEY": "openai-key",
            },
            clear=True,
        ):
            self.assertEqual(select_provider_name(), "built-in")

    def test_gemini_timeout_defaults_and_reads_env(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_gemini_timeout_ms(), DEFAULT_GEMINI_TIMEOUT_MS)
        with patch.dict(os.environ, {"GEMINI_TIMEOUT_MS": "45000"}, clear=True):
            self.assertEqual(get_gemini_timeout_ms(), 45_000)

    def test_gemini_timeout_rejects_invalid_values(self):
        for value in ["abc", "999", "120001"]:
            with self.subTest(value=value):
                with patch.dict(os.environ, {"GEMINI_TIMEOUT_MS": value}, clear=True):
                    with self.assertRaises(ProviderConfigurationError):
                        get_gemini_timeout_ms()
