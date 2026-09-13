"""Retrieval layer.

`Retriever` is the interface the agent depends on. `FTS5Retriever` is today's implementation
(SQLite FTS5 / BM25 full-text search over transcript chunks — see PRD assumption 3 and
architecture.md §2 for why this was chosen over a vector store for this build). A future
`VectorRetriever` (pgvector/Chroma) could implement the same interface without touching the agent
or API layers.
"""
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.services.retrieval.ingest import chunk_episode, iter_episode_files


@dataclass
class RetrievedChunk:
    guest: str
    title: str
    youtube_url: str
    publish_date: str | None
    start_timestamp: str
    chunk_index: int
    episode_slug: str
    text: str
    score: float


class Retriever(Protocol):
    def search(self, query: str, k: int = 6) -> list[RetrievedChunk]: ...
    def chunk_count(self) -> int: ...


_SANITIZE_RE = re.compile(r"[^\w\s]")


def _fts_query(raw_query: str) -> str:
    """Build a safe FTS5 MATCH expression: strip special chars, OR the terms together so
    partial keyword overlap still ranks (BM25 rewards multi-term matches naturally)."""
    terms = [t for t in _SANITIZE_RE.sub(" ", raw_query).split() if len(t) > 1]
    if not terms:
        return '""'
    return " OR ".join(f'"{t}"' for t in terms)


class FTS5Retriever:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_schema()

    def _ensure_schema(self):
        self._conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks
            USING fts5(
                episode_slug, guest, title, youtube_url, publish_date,
                start_timestamp, chunk_index UNINDEXED, text
            )
            """
        )
        self._conn.commit()

    def chunk_count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM transcript_chunks")
        return cur.fetchone()[0]

    def clear(self):
        self._conn.execute("DELETE FROM transcript_chunks")
        self._conn.commit()

    def add_chunks(self, chunks) -> int:
        rows = [
            (
                c.episode_slug, c.guest, c.title, c.youtube_url, c.publish_date or "",
                c.start_timestamp, c.chunk_index, c.text,
            )
            for c in chunks
        ]
        self._conn.executemany(
            """
            INSERT INTO transcript_chunks
                (episode_slug, guest, title, youtube_url, publish_date,
                 start_timestamp, chunk_index, text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return len(rows)

    def search(self, query: str, k: int = 6) -> list[RetrievedChunk]:
        fts = _fts_query(query)
        try:
            cur = self._conn.execute(
                """
                SELECT episode_slug, guest, title, youtube_url, publish_date,
                       start_timestamp, chunk_index, text, bm25(transcript_chunks) as score
                FROM transcript_chunks
                WHERE transcript_chunks MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (fts, k),
            )
        except sqlite3.OperationalError:
            return []
        results = []
        for row in cur.fetchall():
            (episode_slug, guest, title, youtube_url, publish_date,
             start_timestamp, chunk_index, text, score) = row
            results.append(
                RetrievedChunk(
                    guest=guest, title=title, youtube_url=youtube_url,
                    publish_date=publish_date or None, start_timestamp=start_timestamp,
                    chunk_index=chunk_index, episode_slug=episode_slug, text=text,
                    score=float(score),
                )
            )
        return results


def build_index(transcripts_dir: str, index_db_path: str, chunk_target_chars: int = 1000) -> dict:
    """Rebuilds the FTS5 index from transcript files on disk. Returns ingestion stats."""
    retriever = FTS5Retriever(index_db_path)
    retriever.clear()

    episodes_seen = 0
    chunks_added = 0
    skipped = 0

    for path in iter_episode_files(Path(transcripts_dir)):
        episode = chunk_episode(path, chunk_target_chars=chunk_target_chars)
        if episode is None:
            skipped += 1
            continue
        episodes_seen += 1
        chunks_added += retriever.add_chunks(episode.chunks)

    return {
        "episodes_indexed": episodes_seen,
        "episodes_skipped": skipped,
        "chunks_indexed": chunks_added,
    }
