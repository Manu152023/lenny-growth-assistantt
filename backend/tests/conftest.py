import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TEST_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TEST_DIR / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _test_env(tmp_path_factory):
    """Point the app at a throwaway sqlite DB + a tiny fixture transcript index so tests
    never touch real data or require network access."""
    base = tmp_path_factory.mktemp("lenny_test")
    os.environ["DATABASE_URL"] = f"sqlite:///{base}/test.db"
    os.environ["INDEX_DB_PATH"] = str(base / "index.db")
    os.environ["TRANSCRIPTS_DIR"] = str(FIXTURES_DIR / "transcripts")
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ.pop("ANTHROPIC_API_KEY", None)
    from app.config import get_settings
    get_settings.cache_clear()

    from app.deps import get_retriever
    get_retriever.cache_clear()

    from app.services.retrieval.retriever import build_index
    settings = get_settings()
    build_index(settings.transcripts_dir, settings.index_db_path, settings.chunk_target_chars)
    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fake_provider():
    from app.services.llm.base import LLMResult

    class FakeProvider:
        name = "fake"

        def is_available(self):
            return True

        def generate(self, *, system, messages, max_tokens=1500):
            if "Ship 30" in system:
                return LLMResult(text="## Hook\n" + ("word " * 1250), provider="fake", model="fake-1")
            if "produce a single downloadable artifact" in system:
                return LLMResult(
                    text="KIND: markdown\nTITLE: Test Doc\n---\n# Test Doc\ncontent",
                    provider="fake", model="fake-1",
                )
            last_user = messages[-1]["content"]
            if "onboarding" in last_user.lower():
                return LLMResult(
                    text="Ada Chen Rekhi describes activation as the first meaningful action.",
                    provider="fake", model="fake-1",
                )
            return LLMResult(text="I couldn't find this in Lenny's transcripts.", provider="fake", model="fake-1")

    return FakeProvider()
