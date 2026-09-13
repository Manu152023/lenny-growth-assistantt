from __future__ import annotations

import logging

from app.config import Settings
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import LLMProvider, ProviderUnavailableError
from app.services.llm.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


def _build(name: str, settings: Settings) -> LLMProvider:
    if name == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            timeout=settings.llm_request_timeout_seconds,
        )
    if name == "ollama":
        return OllamaProvider(
            host=settings.ollama_host,
            model=settings.ollama_model,
            timeout=settings.llm_request_timeout_seconds,
        )
    raise ValueError(f"Unknown LLM provider '{name}'. Expected 'anthropic' or 'ollama'.")


def get_provider(settings: Settings, override: str | None = None) -> LLMProvider:
    """Returns the provider to use for one request.

    Policy (see architecture.md §6): if the selected provider is unavailable, we do NOT
    silently swap unless `llm_fallback_provider` is explicitly configured. This keeps the
    provider shown in the UI honest.
    """
    name = override or settings.llm_provider
    provider = _build(name, settings)
    if provider.is_available():
        return provider

    if settings.llm_fallback_provider and settings.llm_fallback_provider != name:
        logger.warning(
            "provider_fallback", extra={"fields": {"requested": name, "fallback": settings.llm_fallback_provider}}
        )
        fallback = _build(settings.llm_fallback_provider, settings)
        if fallback.is_available():
            return fallback

    raise ProviderUnavailableError(
        f"LLM provider '{name}' is not available. "
        + (
            "Set ANTHROPIC_API_KEY."
            if name == "anthropic"
            else f"Ensure Ollama is running at the configured host and the model is pulled."
        )
    )


def available_providers(settings: Settings) -> list[str]:
    names = []
    for name in ("anthropic", "ollama"):
        if _build(name, settings).is_available():
            names.append(name)
    return names
