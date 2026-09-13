from datetime import datetime
from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: str
    created_at: datetime


class Citation(BaseModel):
    guest: str
    title: str
    youtube_url: str
    start_timestamp: str
    chunk_index: int
    snippet: str


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    provider: str | None = None
    tool_used: str | None = None
    citations: list[Citation] | None = None
    artifact_id: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionDetail(BaseModel):
    session_id: str
    created_at: datetime
    messages: list[MessageOut]


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    provider_override: str | None = Field(
        default=None, description="Optional per-request override: 'anthropic' | 'ollama'"
    )


class ArtifactOut(BaseModel):
    id: int
    session_id: str
    kind: str
    title: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConfigOut(BaseModel):
    active_provider: str
    available_providers: list[str]
    fallback_provider: str | None
    anthropic_configured: bool
    ollama_reachable: bool
    ollama_model: str
    anthropic_model: str
    index_chunk_count: int


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
