from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.db import get_db
from app.models import Artifact, Session as SessionModel
from app.schemas import ArtifactOut

router = APIRouter(tags=["artifacts"])


@router.get("/sessions/{session_id}/artifacts", response_model=list[ArtifactOut])
def list_artifacts(session_id: str, db: DBSession = Depends(get_db)):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Session not found"})
    return session.artifacts


@router.get("/artifacts/{artifact_id}", response_model=ArtifactOut)
def get_artifact(artifact_id: int, db: DBSession = Depends(get_db)):
    artifact = db.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Artifact not found"})
    return artifact
