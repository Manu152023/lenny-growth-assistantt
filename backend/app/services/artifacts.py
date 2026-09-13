from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.llm.base import LLMProvider
from app.services.retrieval.retriever import RetrievedChunk

SYSTEM_PROMPT = """You produce a single downloadable artifact (a Markdown document or a \
self-contained HTML/CSS snippet) based on the conversation and the grounded transcript \
excerpts provided. Respond in EXACTLY this format, nothing else:

KIND: markdown|html
TITLE: <short title>
---
<the artifact content>

Rules:
- Choose "html" only if the user asked for something visual/interactive (a card, a one-pager \
with styling, a small widget). Otherwise choose "markdown".
- If HTML, the snippet must be fully self-contained (inline <style>, no external network \
requests, no <script> that calls out to any URL) since it will render in a sandboxed iframe \
with no network access.
- Ground factual claims in the provided transcript excerpts; do not invent attributions.
"""

_HEADER_RE = re.compile(
    r"KIND:\s*(markdown|html)\s*\n\s*TITLE:\s*(.+?)\s*\n-{3,}\s*\n(.*)", re.DOTALL | re.IGNORECASE
)


@dataclass
class ArtifactResult:
    kind: str
    title: str
    content: str
    provider: str
    model: str


def _format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(No specific transcript excerpts retrieved for this request.)"
    return "\n\n".join(f"### {c.guest} — {c.title}\n{c.text}" for c in chunks)


def generate_artifact(
    request_text: str,
    conversation_summary: str,
    chunks: list[RetrievedChunk],
    provider: LLMProvider,
    max_tokens: int,
) -> ArtifactResult:
    prompt = (
        f"Conversation so far (summary):\n{conversation_summary}\n\n"
        f"User's artifact request: {request_text}\n\n"
        f"Grounding excerpts:\n{_format_context(chunks)}\n\n"
        "Produce the artifact now, following the required output format exactly."
    )
    result = provider.generate(
        system=SYSTEM_PROMPT, messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens
    )
    match = _HEADER_RE.match(result.text.strip())
    if not match:
        # Fall back gracefully: treat the whole response as a markdown artifact rather than
        # erroring the request out.
        return ArtifactResult(
            kind="markdown", title="Generated document", content=result.text.strip(),
            provider=result.provider, model=result.model,
        )
    kind, title, content = match.groups()
    return ArtifactResult(
        kind=kind.lower().strip(), title=title.strip(), content=content.strip(),
        provider=result.provider, model=result.model,
    )
