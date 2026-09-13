from __future__ import annotations

from app.services.llm.base import LLMResult, ProviderUnavailableError


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None, model: str, timeout: float = 120.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client = None
        if api_key:
            import anthropic  # imported lazily so the package is optional at runtime

            self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    def is_available(self) -> bool:
        return self._client is not None

    def generate(self, *, system: str, messages: list[dict], max_tokens: int = 1500) -> LLMResult:
        if not self._client:
            raise ProviderUnavailableError(
                "Anthropic provider selected but ANTHROPIC_API_KEY is not set."
            )
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a clear 502 upstream
            raise ProviderUnavailableError(f"Anthropic request failed: {exc}") from exc

        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        return LLMResult(text=text, provider=self.name, model=self.model)
