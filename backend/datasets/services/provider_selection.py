import os
from typing import Literal


ProviderName = Literal["gemini", "openai", "built-in"]
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_GEMINI_TIMEOUT_MS = 60_000
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class ProviderConfigurationError(RuntimeError):
    pass


def _has_api_key(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def get_gemini_timeout_ms() -> int:
    raw_value = os.environ.get("GEMINI_TIMEOUT_MS", str(DEFAULT_GEMINI_TIMEOUT_MS))
    try:
        timeout_ms = int(raw_value)
    except ValueError as exc:
        raise ProviderConfigurationError("GEMINI_TIMEOUT_MS must be an integer.") from exc
    if timeout_ms < 1_000 or timeout_ms > 120_000:
        raise ProviderConfigurationError(
            "GEMINI_TIMEOUT_MS must be between 1000 and 120000."
        )
    return timeout_ms


def select_provider_name() -> ProviderName:
    requested = os.environ.get("AI_PROVIDER", "auto").strip().lower()
    if requested not in {"auto", "gemini", "openai", "built-in"}:
        raise ProviderConfigurationError(
            "AI_PROVIDER must be auto, gemini, openai, or built-in."
        )

    if requested == "auto":
        if _has_api_key("GEMINI_API_KEY"):
            return "gemini"
        if _has_api_key("OPENAI_API_KEY"):
            return "openai"
        return "built-in"

    if requested == "gemini" and not _has_api_key("GEMINI_API_KEY"):
        raise ProviderConfigurationError(
            "AI_PROVIDER is set to gemini, but GEMINI_API_KEY is not configured."
        )
    if requested == "openai" and not _has_api_key("OPENAI_API_KEY"):
        raise ProviderConfigurationError(
            "AI_PROVIDER is set to openai, but OPENAI_API_KEY is not configured."
        )
    return requested
