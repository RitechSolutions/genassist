from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationReadReceiptModel(Base):
    """Per-reader high-water mark of the last message a participant has seen.

    One row per ``(conversation_id, reader_role)``: the visitor ("customer") and
    the human "supervisor". ``last_read_sequence`` is the highest transcript
    ``sequence_number`` that reader has seen; a message is "seen by role R" when
    ``message.sequence_number <= receipt[R].last_read_sequence``. The marker only
    ever advances (never moves backwards). The AI agent is never stored here.
    """

    __tablename__ = "conversation_read_receipts"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "reader_role",
            name="uq_conversation_read_receipts_conversation_role",
        ),
    )

    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reader_role: Mapped[str] = mapped_column(String(20), nullable=False)
    reader_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    last_read_sequence: Mapped[int] = mapped_column(
        Integer, nullable=False, default=-1
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self):
        return (
            f"<ConversationReadReceipt(conversation_id={self.conversation_id}, "
            f"reader_role={self.reader_role}, last_read_sequence={self.last_read_sequence})>"
        )
