from functools import lru_cache

from app.config import Settings, get_settings
from app.services.retrieval.retriever import FTS5Retriever, Retriever


@lru_cache
def get_retriever() -> Retriever:
    settings = get_settings()
    return FTS5Retriever(settings.index_db_path)


def get_settings_dep() -> Settings:
    return get_settings()
