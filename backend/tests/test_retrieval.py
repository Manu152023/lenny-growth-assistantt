from app.deps import get_retriever
from app.services.retrieval.ingest import chunk_episode
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures/transcripts/episodes/ada-chen-rekhi/transcript.md"


def test_chunk_episode_parses_frontmatter_and_turns():
    episode = chunk_episode(FIXTURE, chunk_target_chars=1000)
    assert episode is not None
    assert episode.guest == "Ada Chen Rekhi"
    assert episode.youtube_url.endswith("fixture123")
    assert len(episode.chunks) >= 1
    combined = " ".join(c.text for c in episode.chunks)
    assert "aha moment" in combined


def test_retriever_finds_relevant_chunk_with_citation_metadata():
    retriever = get_retriever()
    results = retriever.search("onboarding activation", k=3)
    assert len(results) > 0
    top = results[0]
    assert top.guest == "Ada Chen Rekhi"
    assert top.youtube_url
    assert top.start_timestamp


def test_retriever_returns_empty_for_unrelated_gibberish_query():
    retriever = get_retriever()
    results = retriever.search("zzqqxxnonexistenttoken12345", k=3)
    assert results == []
