from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional



class MessageFeedbackBase(BaseModel):
    message_id: UUID
    feedback: str = Field(..., max_length=50)
    feedback_timestamp: datetime
    feedback_user_id: UUID
    feedback_message: Optional[str] = None

    model_config = ConfigDict(
        from_attributes = True
    )


class MessageFeedbackCreate(MessageFeedbackBase):
    pass

class MessageFeedbackRead(MessageFeedbackBase):
    id: UUID

    model_config = ConfigDict(
        from_attributes = True
    )
