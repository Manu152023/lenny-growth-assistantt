import pytest

from app.config import Settings
from app.services.llm.base import ProviderUnavailableError
from app.services.llm.factory import get_provider


def _settings(**overrides) -> Settings:
    base = dict(
        llm_provider="ollama",
        llm_fallback_provider=None,
        anthropic_api_key=None,
        anthropic_model="claude-sonnet-4-6",
        ollama_host="http://localhost:1",  # unroutable port -> guaranteed unreachable
        ollama_model="llama3.1:8b",
    )
    base.update(overrides)
    return Settings(**base)


def test_ollama_unreachable_raises_clear_error_without_fallback():
    settings = _settings(llm_provider="ollama")
    with pytest.raises(ProviderUnavailableError, match="not available"):
        get_provider(settings)


def test_anthropic_without_api_key_raises_clear_error():
    settings = _settings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(ProviderUnavailableError):
        get_provider(settings)


def test_unknown_provider_name_rejected():
    from app.services.llm.factory import _build
    with pytest.raises(ValueError):
        _build("made-up-provider", _settings())


def test_explicit_fallback_is_not_used_unless_configured():
    """Selecting ollama with no fallback configured must fail loudly, not silently
    succeed some other way — this is the core 'never silently swap provider' guarantee."""
    settings = _settings(llm_provider="ollama", llm_fallback_provider=None)
    with pytest.raises(ProviderUnavailableError):
        get_provider(settings)
