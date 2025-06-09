from app.db.base import Base
from typing import Optional

from sqlalchemy import  UUID, BigInteger, DateTime, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, Text, \
    text, Boolean

from sqlalchemy.orm import Mapped, mapped_column, relationship
import datetime


class ConversationAnalysisModel(Base):
    __tablename__ = 'conversation_analysis'
    __table_args__ = (
        ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name='conversation_id_fk'),
        PrimaryKeyConstraint('id', name='conversation_analysis_pkey'),
    )

    conversation_id: Mapped[UUID] = mapped_column(UUID)
    topic: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    negative_sentiment: Mapped[Optional[int]] = mapped_column(Integer)
    positive_sentiment: Mapped[Optional[int]] = mapped_column(Integer)
    neutral_sentiment: Mapped[Optional[int]] = mapped_column(Integer)
    tone: Mapped[Optional[str]] = mapped_column(String(255))
    customer_satisfaction: Mapped[Optional[int]] = mapped_column(Integer)
    efficiency: Mapped[Optional[int]] = mapped_column(Integer)
    response_time: Mapped[Optional[int]] = mapped_column(Integer)
    quality_of_service: Mapped[Optional[int]] = mapped_column(Integer)
    operator_knowledge: Mapped[Optional[int]] = mapped_column(Integer)
    resolution_rate: Mapped[Optional[int]] = mapped_column(Integer)

    llm_analyst_id: Mapped[Optional[UUID]] = mapped_column(UUID)

    conversation: Mapped["ConversationModel"] = relationship("ConversationModel", back_populates="analysis",
                                                         uselist=False)


class ConversationModel(Base):
    __tablename__ = 'conversations'
    __table_args__ = (
        ForeignKeyConstraint(['operator_id'], ['operators.id'], name='operator_id_fk'),
        ForeignKeyConstraint(['recording_id'], ['recordings.id'], name='recording_id_fk'),
        PrimaryKeyConstraint('id', name='conversations_pkey'),
    )
    
    zendesk_ticket_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)

    data_source_id: Mapped[Optional[UUID]] = mapped_column(UUID)
    operator_id: Mapped[UUID] = mapped_column(UUID)
    recording_id: Mapped[Optional[UUID]] = mapped_column(UUID)
    conversation_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    transcription: Mapped[Optional[str]] = mapped_column(Text)
    customer_id: Mapped[Optional[UUID]] = mapped_column(UUID)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    customer_ratio: Mapped[Optional[int]] = mapped_column(Integer)
    agent_ratio: Mapped[Optional[int]] = mapped_column(Integer)
    duration: Mapped[int] = mapped_column(BigInteger, server_default=text('0'))

    status: Mapped[str] = mapped_column(String(255), server_default='finalized')
    supervisor_id: Mapped[Optional[UUID]] = mapped_column(UUID)
    in_progress_hostility_score: Mapped[int] = mapped_column(Integer, server_default=text('0'))
    conversation_type: Mapped[str] = mapped_column(String(50), nullable=False)


    analysis: Mapped["ConversationAnalysisModel"] = relationship("ConversationAnalysisModel", back_populates="conversation", uselist=False)
    recording = relationship("RecordingModel", back_populates="conversation", uselist=False)
    operator = relationship("OperatorModel", back_populates="conversations")