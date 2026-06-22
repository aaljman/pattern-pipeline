import os
from typing import Literal


ProviderName = Literal["gemini", "openai", "built-in"]
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class ProviderConfigurationError(RuntimeError):
    pass


def _has_api_key(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


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
