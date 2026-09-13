from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.db import get_db
from app.models import Session as SessionModel
from app.schemas import SessionCreateResponse, SessionDetail, MessageOut, Citation

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse, status_code=201)
def create_session(db: DBSession = Depends(get_db)):
    session = SessionModel()
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionCreateResponse(session_id=session.id, created_at=session.created_at)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Session not found"})

    messages_out = []
    for m in session.messages:
        citations = [Citation(**c) for c in m.citations] if m.citations else None
        artifact_id = m.artifacts[0].id if getattr(m, "artifacts", None) else None
        messages_out.append(
            MessageOut(
                id=m.id, role=m.role, content=m.content, provider=m.provider,
                tool_used=m.tool_used, citations=citations, artifact_id=artifact_id,
                created_at=m.created_at,
            )
        )
    return SessionDetail(session_id=session.id, created_at=session.created_at, messages=messages_out)
