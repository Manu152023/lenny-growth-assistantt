from __future__ import annotations

import httpx

from app.services.llm.base import LLMResult, ProviderUnavailableError


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: str, model: str, timeout: float = 120.0):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def generate(self, *, system: str, messages: list[dict], max_tokens: int = 1500) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        try:
            resp = httpx.post(
                f"{self.host}/api/chat", json=payload, timeout=self.timeout
            )
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise ProviderUnavailableError(
                f"Ollama is not reachable at {self.host}. Is it running? "
                f"(`ollama serve`, and `ollama pull {self.model}`)"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Ollama request failed: {exc}") from exc

        data = resp.json()
        text = data.get("message", {}).get("content", "")
        return LLMResult(text=text, provider=self.name, model=self.model)
