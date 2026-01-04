from typing import Optional
from sqlalchemy import ForeignKey, UUID, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from sqlalchemy.dialects.postgresql import JSONB



class LlmAnalystModel(Base):
    __tablename__ = 'llm_analyst'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='llm_analyst_pk'),
        UniqueConstraint('name', name='llm_analyst_unique')
    )

    name: Mapped[Optional[str]] = mapped_column(String(255))
    llm_provider_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("llm_providers.id"), nullable=False)
    prompt: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)

    llm_provider = relationship('LlmProvidersModel', back_populates="llm_analysts", foreign_keys=[llm_provider_id],
                                uselist=False)


class LlmProvidersModel(Base):
    __tablename__ = 'llm_providers'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='llm_providers_pk'),
    )

    name: Mapped[Optional[str]] = mapped_column(String(255))
    llm_model_provider: Mapped[Optional[str]] = mapped_column(String)
    connection_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
    is_default: Mapped[Optional[int]] = mapped_column(Integer)

    llm_model: Mapped[Optional[str]] = mapped_column(String)

    llm_analysts = relationship("LlmAnalystModel", back_populates="llm_provider", foreign_keys=[LlmAnalystModel.llm_provider_id])
    knowledge_bases = relationship("KnowledgeBaseModel", back_populates="llm_provider")
