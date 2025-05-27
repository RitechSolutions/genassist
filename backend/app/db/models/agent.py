from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentModel(Base):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=True)
    llm_provider_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("llm_providers.id"), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text)
    settings: Mapped[str] = mapped_column(JSONB)
    is_active: Mapped[Integer] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[UUID] = mapped_column(ForeignKey("operators.id"), unique=True, nullable=False)
    welcome_message: Mapped[str] = mapped_column(String(500), nullable=False, server_default="Welcome")
    possible_queries: Mapped[str] = mapped_column(String(500), server_default="What can you do?")

    # relationships
    agent_tools = relationship("AgentToolModel", back_populates="agent", foreign_keys="[AgentToolModel.agent_id]", passive_deletes="all")
    agent_knowledge_bases = relationship("AgentKnowledgeBaseModel", back_populates="agent", foreign_keys="["
                                                                                                         "AgentKnowledgeBaseModel.agent_id]", passive_deletes="all")
    llm_provider = relationship("LlmProvidersModel", back_populates="agents")
    operator = relationship("OperatorModel", back_populates="agent", uselist=False)

