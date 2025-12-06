from datetime import datetime
from uuid import UUID
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, Integer, UUID as SQLAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class TranscriptMessageModel(Base):
    """Individual message within a conversation transcript"""
    __tablename__ = 'transcript_messages'

    conversation_id: Mapped[UUID] = mapped_column(
            SQLAlchemyUUID,
            ForeignKey('conversations.id', ondelete='CASCADE'),
            nullable=False,
            index=True
            )
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    speaker: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Sequence number for ordering messages within a conversation
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    conversation: Mapped["ConversationModel"] = relationship(
            "ConversationModel",
            back_populates="messages"
            )
    feedback: Mapped[list["MessageFeedbackModel"]] = relationship(
            "MessageFeedbackModel",
            back_populates="message",
            cascade="all, delete-orphan"
            )


    def __repr__(self):
        return f"<TranscriptMessage(id={self.id}, id={self.id}, speaker={self.speaker})>"


class MessageFeedbackModel(Base):
    """Feedback on individual messages"""
    __tablename__ = 'message_feedback'

    # Note: id (UUID primary key) is inherited from Base class

    message_id: Mapped[UUID] = mapped_column(
            SQLAlchemyUUID,
            ForeignKey('transcript_messages.id', ondelete='CASCADE'),
            nullable=False,
            index=True
            )
    feedback: Mapped[str] = mapped_column(String(50), nullable=False)
    feedback_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feedback_user_id: Mapped[UUID] = mapped_column(SQLAlchemyUUID, nullable=False)
    feedback_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationship
    message: Mapped["TranscriptMessageModel"] = relationship(
            "TranscriptMessageModel",
            back_populates="feedback"
            )


    def __repr__(self):
        return f"<MessageFeedback(id={self.id}, feedback={self.feedback}, user={self.feedback_user_id})>"