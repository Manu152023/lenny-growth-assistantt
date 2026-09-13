from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider is selected but cannot serve a request (missing key,
    unreachable host, etc). Mapped to HTTP 503 at the API layer."""


class LLMProvider(Protocol):
    name: str

    def generate(
        self, *, system: str, messages: list[dict], max_tokens: int = 1500
    ) -> LLMResult: ...

    def is_available(self) -> bool: ...
