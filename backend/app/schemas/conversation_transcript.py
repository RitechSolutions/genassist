from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.utils.enums.message_feedback_enum import Feedback


@dataclass
class TranscriptSegment:
    start_time: float
    speaker: str
    text: str
    end_time: float = 0.0


class TranscriptSegmentInput(BaseModel):
    create_time: Optional[datetime] = None
    start_time: float
    end_time: float
    speaker: str
    text: str
    type: Optional[str] = "message"

    model_config = ConfigDict(
            from_attributes=True,
            )


class TranscriptSegmentFeedback(BaseModel):
    feedback: Feedback = Field(...)
    feedback_message: str = Field(None)

    model_config = ConfigDict(
            from_attributes=True,
            )


class ConversationTranscriptBase(BaseModel):
    conversation_id: Optional[UUID] = None
    thread_id: Optional[UUID] = None
    messages: List[TranscriptSegmentInput]
    operator_id: UUID
    data_source_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    llm_analyst_id: Optional[UUID] = None
    recorded_at: Optional[datetime] = None


class ConversationTranscriptCreate(ConversationTranscriptBase):
    operator_id: Optional[UUID] = None


class InProgConvTranscrUpdate(BaseModel):
    """
    Model for updating an existing in-progress conversation
    by adding more transcript chunks.
    """
    messages: List[TranscriptSegmentInput]
    metadata: Optional[dict] = None
    llm_analyst_id: Optional[UUID] = None


class InProgressConversationTranscriptFinalize(BaseModel):
    llm_analyst_id: Optional[UUID] = None
