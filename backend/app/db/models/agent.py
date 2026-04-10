from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, LargeBinary, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentModel(Base):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[Integer] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey("operators.id"), unique=True, nullable=False)
    welcome_message: Mapped[str] = mapped_column(String(500), nullable=False, server_default="Welcome")
    welcome_image: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    welcome_title: Mapped[str] = mapped_column(String(200), nullable=True)
    possible_queries: Mapped[str] = mapped_column(String(500), server_default="What can you do?")
    thinking_phrases: Mapped[str] = mapped_column(String(500), server_default="Thinking...")
    thinking_phrase_delay: Mapped[Integer] = mapped_column(Integer, nullable=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id"), nullable=True)
    input_disclaimer_html: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    llm_analyst_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Relationships
    operator = relationship("OperatorModel", back_populates="agent", uselist=False)
    workflow = relationship("WorkflowModel", back_populates="agent", uselist=False)
    security_settings = relationship(
        "AgentSecuritySettingsModel",
        back_populates="agent",
        uselist=False,
        cascade="all, delete-orphan"
    )
