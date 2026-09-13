from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.deps import get_retriever
from app.schemas import ConfigOut
from app.services.llm.factory import available_providers
from app.services.llm.ollama_provider import OllamaProvider

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigOut)
def get_config(settings: Settings = Depends(get_settings)):
    retriever = get_retriever()
    ollama = OllamaProvider(settings.ollama_host, settings.ollama_model)
    return ConfigOut(
        active_provider=settings.llm_provider,
        available_providers=available_providers(settings),
        fallback_provider=settings.llm_fallback_provider,
        anthropic_configured=bool(settings.anthropic_api_key),
        ollama_reachable=ollama.is_available(),
        ollama_model=settings.ollama_model,
        anthropic_model=settings.anthropic_model,
        index_chunk_count=retriever.chunk_count(),
    )
