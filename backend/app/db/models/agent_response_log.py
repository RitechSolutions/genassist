from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
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

    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Optional convenience relationships
    message = relationship("TranscriptMessageModel", lazy="joined")
    conversation = relationship("ConversationModel", lazy="joined")

