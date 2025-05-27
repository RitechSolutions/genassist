from uuid import UUID
from pydantic import BaseModel, Field

class QuestionBase(BaseModel):
    conversation_id: UUID = Field(..., title="Conversation ID")
    question: str = Field(..., title="Question")

class QuestionCreate(QuestionBase):
    pass