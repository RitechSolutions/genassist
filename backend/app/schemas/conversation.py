from uuid import UUID
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

from app.schemas.conversation_analysis import ConversationAnalysisRead
from app.schemas.recording import RecordingRead


class ConversationBase(BaseModel):
    operator_id: UUID
    data_source_id: UUID | None = None
    recording_id: Optional[UUID]
    transcription: str
    conversation_date: Optional[datetime]
    customer_id: Optional[UUID] | None = None
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
    pass

class ConversationRead(ConversationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    recording: Optional[RecordingRead] = None
    analysis: Optional[ConversationAnalysisRead] = None
    in_progress_hostility_score: Optional[int] = None
    supervisor_id: Optional[UUID] = None


    model_config = ConfigDict(
        from_attributes = True
    )
