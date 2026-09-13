from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.config import get_settings, Settings
from app.db import db_healthy
from app.deps import get_retriever
from app.services.llm.factory import available_providers

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(settings: Settings = Depends(get_settings)):
    retriever = get_retriever()
    checks = {
        "database": db_healthy(),
        "index_populated": retriever.chunk_count() > 0,
        "llm_provider_reachable": settings.llm_provider in available_providers(settings),
    }
    ok = all(checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"ready": ok, "checks": checks})
