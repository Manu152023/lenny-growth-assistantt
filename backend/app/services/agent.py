"""Agent / tool router.

Deliberately a small, explicit, inspectable router rather than a black-box planner — see
architecture.md §3 for why. Three tools:

  - "chat"          grounded Q&A over transcripts, with citations and abstention
  - "ship30_essay"  the Ship 30 for 30 writing skill
  - "artifact"      general Markdown/HTML artifact generation

Each tool re-runs retrieval for the current turn (follow-ups are not stuck with turn-1 context).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.config import Settings
from app.services.llm.base import LLMProvider
from app.services.retrieval.retriever import Retriever, RetrievedChunk
from app.services.skills import ship30
from app.services import artifacts as artifact_service

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are the Lenny Growth Assistant, a product/growth research assistant \
grounded ONLY in the provided excerpts from Lenny's Podcast transcripts.

Rules:
1. Answer using only the information in the excerpts below. You may phrase it in your own words \
and synthesize across multiple excerpts.
2. If the excerpts don't actually answer the question, say plainly: "I couldn't find this in \
Lenny's transcripts" and briefly say what related topics ARE covered, if anything is close. \
Do not fill gaps with general knowledge.
3. When you use a specific claim, mention which guest it came from in your own sentence (e.g. \
"Brian Balfour describes..."). You do not need to produce a formal citation list — the app \
attaches exact sources separately.
4. Be concise and concrete. Prefer specific frameworks/examples over generic advice.
"""

SHIP30_TRIGGERS = [
    r"ship\s*30", r"ship30", r"turn (this|that|it) into (a|an) (essay|post)",
    r"write (this|that|it) as an essay", r"atomic essay",
]
ARTIFACT_TRIGGERS = [
    r"make (this|that|it) (a|an|into a)? ?(doc|document|one[- ]pager|page|card|artifact)",
    r"turn (this|that|it) into (a|an) (doc|document|html|markdown|page)",
    r"give me (an? )?(html|markdown|md) (page|card|snippet|doc|document)",
    r"generate (an? )?artifact",
    r"write (this|it) up",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


@dataclass
class AgentResponse:
    tool_used: str
    content: str
    provider: str
    model: str
    citations: list[RetrievedChunk]
    artifact: artifact_service.ArtifactResult | None = None


def classify_intent(user_text: str) -> str:
    if _matches_any(SHIP30_TRIGGERS, user_text):
        return "ship30_essay"
    if _matches_any(ARTIFACT_TRIGGERS, user_text):
        return "artifact"
    return "chat"


def _format_chat_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(No matching transcript excerpts were found for this query.)"
    return "\n\n".join(
        f"[{i+1}] {c.guest} — {c.title} (from {c.start_timestamp})\n{c.text}"
        for i, c in enumerate(chunks)
    )


def _conversation_summary(history: list[dict]) -> str:
    # Cheap, deterministic summary for the artifact tool's prompt: last few turns verbatim.
    tail = history[-6:]
    return "\n".join(f"{m['role']}: {m['content']}" for m in tail)


def run_turn(
    user_text: str,
    history: list[dict],
    retriever: Retriever,
    provider: LLMProvider,
    settings: Settings,
) -> AgentResponse:
    intent = classify_intent(user_text)
    top_k = settings.retrieval_top_k

    if intent == "ship30_essay":
        chunks = retriever.search(user_text, k=top_k)
        result = ship30.write_ship30_essay(
            topic=user_text, chunks=chunks, provider=provider, max_tokens=settings.llm_max_tokens
        )
        artifact = artifact_service.ArtifactResult(
            kind="markdown", title="Ship 30 for 30 draft", content=result.markdown,
            provider=result.provider, model=result.model,
        )
        summary = (
            f"Drafted a Ship 30 for 30 essay (~{result.word_count} words). "
            "See the artifact panel for the full piece."
        )
        return AgentResponse(
            tool_used="ship30_essay", content=summary, provider=result.provider,
            model=result.model, citations=chunks, artifact=artifact,
        )

    if intent == "artifact":
        chunks = retriever.search(user_text, k=top_k)
        result = artifact_service.generate_artifact(
            request_text=user_text,
            conversation_summary=_conversation_summary(history),
            chunks=chunks,
            provider=provider,
            max_tokens=settings.llm_max_tokens,
        )
        summary = f'Created a {result.kind.upper()} artifact: "{result.title}". See the artifact panel.'
        return AgentResponse(
            tool_used="artifact", content=summary, provider=result.provider, model=result.model,
            citations=chunks, artifact=result,
        )

    # default: grounded chat
    chunks = retriever.search(user_text, k=top_k)
    context = _format_chat_context(chunks)
    messages = [*history, {"role": "user", "content": f"Transcript excerpts:\n{context}\n\nQuestion: {user_text}"}]
    result = provider.generate(
        system=CHAT_SYSTEM_PROMPT, messages=messages, max_tokens=settings.llm_max_tokens
    )
    return AgentResponse(
        tool_used="chat", content=result.text, provider=result.provider, model=result.model,
        citations=chunks if chunks else [],
    )
