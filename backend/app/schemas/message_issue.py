from datetime import date, datetime
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class ReportedIssueRead(BaseModel):
    """A message that an admin/supervisor commented on, plus its resolution status
    and the context needed to navigate to the conversation or the agent's workflow."""

    # ``feedback_id`` is the message_feedback (comment) row id — the issue key.
    feedback_id: UUID
    message_id: UUID
    conversation_id: UUID
    agent_id: Optional[UUID] = None
    workflow_name: Optional[str] = None
    text: str
    speaker: str
    comment: str
    rating: Optional[str] = None
    status: str
    reported_by: Optional[str] = None
    reported_at: datetime
    conversation_topic: Optional[str] = None
    conversation_subtopic: Optional[str] = None
    conversation_date: Optional[datetime] = None
    fix_version: Optional[str] = None
    target_rollout_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class IssueStatusUpdate(BaseModel):
    """Body for changing a reported issue's status."""

    status: str = Field(..., max_length=50)


class IssueUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=50)
    fix_version: Optional[str] = Field(None, max_length=100)
    target_rollout_date: Optional[date] = None

    @field_validator("fix_version", mode="before")
    @classmethod
    def blank_to_none(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("status", mode="before")
    @classmethod
    def status_not_null(cls, value):
        if value is None:
            raise ValueError("status cannot be null")
        return value


class MessageIssueRead(BaseModel):
    id: UUID
    message_feedback_id: UUID
    status: str
    fix_version: Optional[str] = None
    target_rollout_date: Optional[date] = None
    resolved_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IssueStatusSummary(BaseModel):
    total: int
    by_status: dict[str, int]


class IssueNoteCreate(BaseModel):
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class IssueNoteRead(BaseModel):
    id: UUID
    message_feedback_id: UUID
    author_user_id: UUID
    author_username: Optional[str] = None
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
