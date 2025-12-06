import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeBaseModel(Base):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ─────────────────────────── file / raw content info ──────────────────────
    type: Mapped[str] = mapped_column(String(20))  # "file" | "url" | …
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    files: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ─────────────────────────────── configs (JSONB) ──────────────────────────
    vector_store: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rag_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    legra_finalize: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    embeddings_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # sync configuration
    sync_active: Mapped[Optional[int]] = mapped_column(Integer)
    sync_source_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("data_sources.id"), nullable=True
    )
    llm_provider_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("llm_providers.id"), nullable=True
    )

    last_synced: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    last_sync_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_file_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    sync_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Define the relationship to DataSourceModel and LlmProvidersModel
    sync_source = relationship("DataSourceModel", back_populates="knowledge_bases")
    llm_provider = relationship("LlmProvidersModel", back_populates="knowledge_bases")
