import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UUID as SQLAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageIssueModel(Base):
    """Tracks the resolution status of an issue reported as a comment on a message.

    One row per tracked comment (``message_feedback`` row). Rows are created lazily
    the first time an admin/supervisor changes a comment's status away from the
    implicit default ('open') or fills in its triage fields.
    """

    __tablename__ = "message_issues"

    message_feedback_id: Mapped[UUID] = mapped_column(
        SQLAlchemyUUID,
        ForeignKey("message_feedback.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="open"
    )
    resolved_by: Mapped[Optional[UUID]] = mapped_column(SQLAlchemyUUID, nullable=True)
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fix_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_rollout_date: Mapped[Optional[datetime.date]] = mapped_column(
        Date, nullable=True
    )

    feedback = relationship("MessageFeedbackModel")

    def __repr__(self):
        return (
            f"<MessageIssue(id={self.id}, "
            f"message_feedback_id={self.message_feedback_id}, status={self.status})>"
        )


class MessageIssueNoteModel(Base):
    __tablename__ = "message_issue_notes"

    message_feedback_id: Mapped[UUID] = mapped_column(
        SQLAlchemyUUID,
        ForeignKey("message_feedback.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[UUID] = mapped_column(
        SQLAlchemyUUID, ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
