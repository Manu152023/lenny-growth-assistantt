import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_retriever
from app.logging_config import log_event
from app.models import Session as SessionModel, Message, Artifact
from app.schemas import MessageCreateRequest, MessageOut, Citation
from app.services.agent import run_turn
from app.services.llm.base import ProviderUnavailableError
from app.services.llm.factory import get_provider
from app.services.retrieval.retriever import Retriever

router = APIRouter(prefix="/sessions", tags=["chat"])
logger = logging.getLogger(__name__)


def _history_for_llm(session: SessionModel) -> list[dict]:
    return [
        {"role": m.role, "content": m.content}
        for m in session.messages
        if m.role in ("user", "assistant")
    ]


@router.post("/{session_id}/messages", response_model=MessageOut, status_code=201)
def post_message(
    session_id: str,
    body: MessageCreateRequest,
    db: DBSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    retriever: Retriever = Depends(get_retriever),
):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Session not found"})

    user_msg = Message(session_id=session_id, role="user", content=body.content)
    db.add(user_msg)
    db.commit()
    db.refresh(session)

    history = _history_for_llm(session)[:-1]  # exclude the message we just added; agent re-adds it

    try:
        provider = get_provider(settings, override=body.provider_override)
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail={"code": "provider_unavailable", "message": str(exc)})

    try:
        result = run_turn(
            user_text=body.content, history=history, retriever=retriever,
            provider=provider, settings=settings,
        )
    except ProviderUnavailableError as exc:
        log_event(logger, logging.ERROR, "llm_provider_error", session_id=session_id, error=str(exc))
        raise HTTPException(status_code=502, detail={"code": "llm_error", "message": str(exc)})
    except Exception as exc:  # noqa: BLE001
        log_event(logger, logging.ERROR, "agent_turn_failed", session_id=session_id, error=str(exc))
        raise HTTPException(
            status_code=500, detail={"code": "internal_error", "message": "The assistant failed to respond."}
        )

    citations_payload = [
        {
            "guest": c.guest, "title": c.title, "youtube_url": c.youtube_url,
            "start_timestamp": c.start_timestamp, "chunk_index": c.chunk_index,
            "snippet": c.text[:220],
        }
        for c in result.citations
    ]

    assistant_msg = Message(
        session_id=session_id, role="assistant", content=result.content,
        provider=result.provider, tool_used=result.tool_used,
        citations=citations_payload or None,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    artifact_id = None
    if result.artifact is not None:
        artifact = Artifact(
            session_id=session_id, message_id=assistant_msg.id,
            kind=result.artifact.kind, title=result.artifact.title,
            content=result.artifact.content,
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        artifact_id = artifact.id

    log_event(
        logger, logging.INFO, "chat_turn_completed", session_id=session_id,
        tool_used=result.tool_used, provider=result.provider, citation_count=len(result.citations),
    )

    return MessageOut(
        id=assistant_msg.id, role="assistant", content=assistant_msg.content,
        provider=assistant_msg.provider, tool_used=assistant_msg.tool_used,
        citations=[Citation(**c) for c in citations_payload] if citations_payload else None,
        artifact_id=artifact_id, created_at=assistant_msg.created_at,
    )
