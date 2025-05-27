from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentKnowledgeBaseModel(Base):
    __tablename__ = "agent_knowledge_bases"

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)

    # relationships
    agent = relationship("AgentModel", back_populates="agent_knowledge_bases", foreign_keys=[agent_id])
    knowledge_base = relationship("KnowledgeBaseModel", back_populates="agent_knowledge_bases",
                                  foreign_keys=[knowledge_base_id])
