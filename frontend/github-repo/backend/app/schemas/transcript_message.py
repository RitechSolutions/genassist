from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from app.schemas.message_feedback import MessageFeedbackRead


class TranscriptMessageBase(BaseModel):
    create_time: Optional[datetime] = None
    start_time: float
    end_time: float
    speaker: str = Field(..., max_length=50)
    text: str
    type: str = Field(..., max_length=50)


    model_config = ConfigDict(
        from_attributes = True
    )


class TranscriptMessageCreate(TranscriptMessageBase):
    pass

class TranscriptMessageRead(TranscriptMessageBase):
    id: UUID
    feedback: Optional[list[MessageFeedbackRead]] = None

    model_config = ConfigDict(
        from_attributes = True
    )
