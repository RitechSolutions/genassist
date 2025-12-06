from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentModel(Base):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[Integer] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("operators.id"), unique=True, nullable=False
    )
    welcome_message: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default="Welcome"
    )
    welcome_image: Mapped[bytes] = mapped_column(LargeBinary, nullable=True)
    welcome_title: Mapped[str] = mapped_column(String(200), nullable=True)
    possible_queries: Mapped[str] = mapped_column(
        String(500), server_default="What can you do?"
    )
    thinking_phrases: Mapped[str] = mapped_column(
        String(500), server_default="Thinking..."
    )
    thinking_phrase_delay: Mapped[Integer] = mapped_column(Integer, nullable=True)
    workflow_id: Mapped[UUID] = mapped_column(ForeignKey("workflows.id"), nullable=True)

    # Relationships
    operator = relationship("OperatorModel", back_populates="agent", uselist=False)
    workflow = relationship("WorkflowModel", back_populates="agent", uselist=False)
