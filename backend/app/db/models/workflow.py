from typing import List

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class WorkflowModel(Base):
    __tablename__ = "workflows"

    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    nodes: Mapped[List[dict] | None] = mapped_column(
        JSONB, nullable=True
    )  # JSON configuration for the workflow
    edges: Mapped[List[dict] | None] = mapped_column(
        JSONB, nullable=True
    )  # JSON configuration for the workflow
    testInput: Mapped[List[dict] | None] = mapped_column(
        JSONB, nullable=True
    )  # JSON configuration for the workflow
    executionState: Mapped[List[dict] | None] = mapped_column(
        JSONB, nullable=True
    )  # JSON configuration for the workflow
    version = Column(String, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    agent_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Relationships
    user = relationship("UserModel", back_populates="workflows")
    agent = relationship("AgentModel", back_populates="workflow", uselist=False)
