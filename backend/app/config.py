"""Central configuration. Every knob the evaluator needs to change lives here and is
read from environment variables so behavior can change without touching code."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Persistence -------------------------------------------------
    # Defaults to a local SQLite file so `docker compose up` / bare `uvicorn` both work
    # with zero external setup. Point this at Postgres (Supabase/Railway/local) in prod.
    database_url: str = "sqlite:///./data/app.db"

    # --- Retrieval index ----------------------------------------------
    transcripts_repo_url: str = "https://github.com/ChatPRD/lennys-podcast-transcripts"
    transcripts_dir: str = "./data/transcripts"
    index_db_path: str = "./data/index.db"
    retrieval_top_k: int = 6
    chunk_target_chars: int = 1000

    # --- LLM providers --------------------------------------------------
    llm_provider: str = "ollama"          # "anthropic" | "ollama" — active provider
    llm_fallback_provider: str | None = None  # e.g. "ollama" — opt-in auto-fallback

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    llm_request_timeout_seconds: float = 120.0
    llm_max_tokens: int = 1500

    # --- App -------------------------------------------------------------
    cors_origins: str = "*"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
