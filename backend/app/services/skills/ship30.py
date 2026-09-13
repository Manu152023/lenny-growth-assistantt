"""Ship 30 for 30 essay skill.

Writing rules below are encoded as a structured spec (per PRD requirement 4.2: "encode them in
the skill rather than relying on an unstructured one-off prompt"), derived from the linked guide
(https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide)
and the assignment's stated acceptance criteria:

- a strong hook in the first 1-2 sentences (a claim, question, or specific stat/story)
- clear narrative progression (setup -> tension/insight -> resolution), not a listicle dump
- skimmable formatting: headings, bullets, selective **bold** for the load-bearing phrases
- ~1,250 words
- one specific, useful, restatable takeaway at the end
- every non-obvious claim traceable to a retrieved transcript chunk
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.llm.base import LLMProvider
from app.services.retrieval.retriever import RetrievedChunk

TARGET_WORDS = 1250
WORD_TOLERANCE = 250  # regenerate once if further off than this

SYSTEM_PROMPT = """You are a writing skill that converts research from Lenny's Podcast \
transcripts into a Ship 30 for 30 style essay (atomic essay format for online writing).

Hard requirements for every essay you write:
1. HOOK: Open with 1-2 sentences that are a bold claim, a sharp question, or a specific concrete \
detail — never a generic throat-clear like "In today's fast-paced world...".
2. NARRATIVE PROGRESSION: The essay must move somewhere — a setup, a turn/insight, and a \
resolution — not just a list of unconnected tips.
3. SKIMMABLE FORMATTING: Use Markdown headings (##), bullet points where they clarify, and \
**bold** on the handful of phrases that carry the most weight. Do not bold everything.
4. LENGTH: Aim for approximately 1,250 words.
5. ONE TAKEAWAY: End with a short, specific, restatable takeaway the reader could apply today — \
not a vague "hope this helps."
6. GROUNDING: Only use claims, frameworks, quotes, or examples that appear in the provided \
transcript excerpts below. Attribute ideas to the guest by name in the prose itself \
(e.g. "As Wes Kao put it..."). If the excerpts don't support a strong essay, say so plainly \
instead of inventing material.

Output ONLY the essay in Markdown. Do not include meta-commentary about what you did.
"""


@dataclass
class Ship30Result:
    markdown: str
    word_count: int
    provider: str
    model: str


def _format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(No relevant transcript excerpts were found.)"
    parts = []
    for c in chunks:
        parts.append(
            f"### {c.guest} — {c.title} (from {c.start_timestamp})\n{c.text}"
        )
    return "\n\n".join(parts)


def _build_prompt(topic: str, chunks: list[RetrievedChunk], length_note: str = "") -> str:
    context = _format_context(chunks)
    return (
        f"Topic / request: {topic}\n\n"
        f"Transcript excerpts to ground the essay in:\n\n{context}\n\n"
        f"Write the Ship 30 for 30 essay now.{(' ' + length_note) if length_note else ''}"
    )


def write_ship30_essay(
    topic: str, chunks: list[RetrievedChunk], provider: LLMProvider, max_tokens: int
) -> Ship30Result:
    prompt = _build_prompt(topic, chunks)
    result = provider.generate(
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    word_count = len(result.text.split())

    if abs(word_count - TARGET_WORDS) > WORD_TOLERANCE:
        direction = "shorter, tighter" if word_count > TARGET_WORDS else "longer, more developed"
        note = (
            f"Your previous draft was {word_count} words; the target is ~{TARGET_WORDS}. "
            f"Rewrite it {direction}, keeping the same hook and takeaway."
        )
        retry_prompt = _build_prompt(topic, chunks, length_note=note)
        result = provider.generate(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": retry_prompt}],
            max_tokens=max_tokens,
        )
        word_count = len(result.text.split())

    return Ship30Result(
        markdown=result.text, word_count=word_count, provider=result.provider, model=result.model
    )
