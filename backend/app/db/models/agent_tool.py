from uuid import UUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentToolModel(Base):
    __tablename__ = "agent_tools"

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    tool_id: Mapped[UUID] = mapped_column(ForeignKey("tools.id", ondelete="CASCADE"), nullable=False)

    # relationships
    agent = relationship("AgentModel", back_populates="agent_tools", foreign_keys=[agent_id])
    tool = relationship("ToolModel", back_populates="agent_tools", foreign_keys=[tool_id])
