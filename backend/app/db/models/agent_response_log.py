from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentResponseLogModel(Base):
    """
    Stores the full raw agent response payload for a given transcript message.

    This is intended purely for debugging/traceability so we can later inspect
    exactly what the agent returned when a specific transcript message was created.
    """

    __tablename__ = "agent_response_logs"

    # Declared here so Alembic autogenerate knows these
    # partial indexes belong to the model and does not try to drop them
    __table_args__ = (
        Index(
            "uq_agent_response_logs_workflow_execution_id",
            "workflow_execution_id",
            unique=True,
            postgresql_where="workflow_execution_id IS NOT NULL",
        ),
        Index(
            "ix_agent_response_logs_logged_at",
            "logged_at",
            postgresql_where="is_deleted = 0",
        ),
    )

    transcript_message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("transcript_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    raw_response: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Full JSON-serialized agent_response as returned from the agent.",
    )

    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    workflow_execution_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Optional convenience relationships
    message = relationship("TranscriptMessageModel", lazy="joined")
    conversation = relationship("ConversationModel", lazy="joined")

