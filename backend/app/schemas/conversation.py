from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

from app.schemas.conversation_analysis import ConversationAnalysisRead
from app.schemas.recording import RecordingRead
from app.schemas.transcript_message import TranscriptMessageRead
from app.schemas.agent_security_settings import AgentSecuritySettingsUpdate


class AgentMinimalForCache(BaseModel):
    """Minimal agent schema for caching - contains only fields needed for security checks."""
    id: UUID
    name: str
    is_active: bool = False
    security_settings: Optional[AgentSecuritySettingsUpdate] = None

    model_config = ConfigDict(from_attributes=True)


class OperatorWithAgentForCache(BaseModel):
    """Operator schema with nested agent for caching."""
    id: UUID
    agent: Optional[AgentMinimalForCache] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationWithOperatorAgentRead(BaseModel):
    """Conversation schema with operator and agent for caching in security dependencies."""
    id: UUID
    operator_id: UUID
    operator: Optional[OperatorWithAgentForCache] = None
    model_config = ConfigDict(from_attributes=True)


class ConversationBase(BaseModel):
    operator_id: UUID
    data_source_id: UUID | None = None
    recording_id: Optional[UUID]
    transcription: Optional[str] = None
    conversation_date: Optional[datetime]
    customer_id: Optional[UUID] | None = None
    thread_id: Optional[UUID] = None
    word_count: Optional[int] = None
    customer_ratio: Optional[int] = None
    agent_ratio: Optional[int] = None
    duration: Optional[int] = None
    status: Optional[str] = None
    conversation_type: Optional[str] = None

    model_config = ConfigDict(
        from_attributes = True
    )


class ConversationCreate(ConversationBase):
    id: Optional[UUID] = None

class ConversationRead(ConversationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    recording: Optional[RecordingRead] = None
    analysis: Optional[ConversationAnalysisRead] = None
    in_progress_hostility_score: Optional[int] = None
    supervisor_id: Optional[UUID] = None
    topic: Optional[str] = None
    negative_reason: Optional[str] = None
    feedback: Optional[str] = None
    messages: Optional[list[TranscriptMessageRead]] = None


    model_config = ConfigDict(
        from_attributes = True
    )
