"""Parses Lenny's Podcast transcript markdown files into citable chunks.

File format (confirmed against the source repo):

    ---
    guest: Boz
    title: Making Meta | Andrew 'Boz' Bosworth (CTO)
    youtube_url: https://www.youtube.com/watch?v=...
    publish_date: 2024-03-03
    ...
    ---

    # <title>

    ## Transcript

    Lenny (00:00:00):
    <text...>

    Boz (00:01:12):
    <text...>
    ...

We group consecutive speaker turns into chunks of ~`chunk_target_chars` characters (never
splitting a turn's text across two chunks) so each chunk stays coherent and citable back to a
timestamp.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

TURN_RE = re.compile(r"^([A-Za-z0-9 ,.'\-]+?)\s*\((\d{1,2}:\d{2}(?::\d{2})?)\):\s*$")


@dataclass
class TranscriptChunk:
    episode_slug: str
    guest: str
    title: str
    youtube_url: str
    publish_date: str | None
    start_timestamp: str
    chunk_index: int
    text: str


@dataclass
class ParsedEpisode:
    slug: str
    guest: str
    title: str
    youtube_url: str
    publish_date: str | None
    chunks: list[TranscriptChunk] = field(default_factory=list)


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Split a `---\\n...\\n---\\n` YAML frontmatter block from the rest of the file."""
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    _, fm_raw, body = parts
    try:
        meta = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, body


def _parse_turns(body: str) -> list[tuple[str, str, str]]:
    """Returns a list of (speaker, timestamp, text) for each speaker turn found after the
    '## Transcript' heading (or the whole body if that heading isn't present)."""
    if "## Transcript" in body:
        body = body.split("## Transcript", 1)[1]

    lines = body.splitlines()
    turns: list[tuple[str, str, str]] = []
    current_speaker = None
    current_ts = None
    current_text: list[str] = []

    def flush():
        if current_speaker is not None:
            text = " ".join(t.strip() for t in current_text if t.strip())
            if text:
                turns.append((current_speaker, current_ts, text))

    for line in lines:
        m = TURN_RE.match(line.strip())
        if m:
            flush()
            current_speaker, current_ts = m.group(1).strip(), m.group(2).strip()
            current_text = []
        else:
            current_text.append(line)
    flush()
    return turns


def chunk_episode(path: Path, chunk_target_chars: int = 1000) -> ParsedEpisode | None:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    meta, body = _parse_frontmatter(raw)
    if not meta:
        return None

    slug = path.parent.name
    guest = str(meta.get("guest") or slug)
    title = str(meta.get("title") or guest)
    youtube_url = str(meta.get("youtube_url") or "")
    publish_date = meta.get("publish_date")
    publish_date = str(publish_date) if publish_date else None

    turns = _parse_turns(body)
    episode = ParsedEpisode(
        slug=slug, guest=guest, title=title, youtube_url=youtube_url, publish_date=publish_date
    )

    buf: list[str] = []
    buf_len = 0
    buf_start_ts = None
    chunk_index = 0

    def flush_chunk():
        nonlocal buf, buf_len, buf_start_ts, chunk_index
        if not buf:
            return
        episode.chunks.append(
            TranscriptChunk(
                episode_slug=slug,
                guest=guest,
                title=title,
                youtube_url=youtube_url,
                publish_date=publish_date,
                start_timestamp=buf_start_ts or "00:00:00",
                chunk_index=chunk_index,
                text="\n".join(buf),
            )
        )
        chunk_index += 1
        buf = []
        buf_len = 0
        buf_start_ts = None

    for speaker, ts, text in turns:
        line = f"{speaker} ({ts}): {text}"
        if buf_start_ts is None:
            buf_start_ts = ts
        if buf_len + len(line) > chunk_target_chars and buf:
            flush_chunk()
            buf_start_ts = ts
        buf.append(line)
        buf_len += len(line)
    flush_chunk()

    return episode if episode.chunks else None


def iter_episode_files(transcripts_dir: Path):
    episodes_dir = transcripts_dir / "episodes"
    if not episodes_dir.exists():
        return
    for transcript_path in sorted(episodes_dir.glob("*/transcript.md")):
        yield transcript_path
