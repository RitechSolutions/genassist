from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.utils.enums.issue_status_enum import IssueStatus


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
    conversation_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IssueStatusUpdate(BaseModel):
    """Body for changing a reported issue's status."""

    status: IssueStatus
