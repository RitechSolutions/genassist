"""Tables that store LLM token and cost usage"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

RUN_STATUSES = ("completed", "failed", "paused", "idle", "running")

CONTROL_SINGLETON_KEY = "singleton"


class LlmUsageEventModel(Base):
    """One LLM call. ``cost_usd`` stays NULL for unpriced calls"""

    __tablename__ = "llm_usage_events"
    __table_args__ = (
        UniqueConstraint("execution_id", "call_index", name="uq_llm_usage_events_execution_call"),
        Index(
            "uq_llm_usage_events_legacy_log",
            "legacy_response_log_id",
            unique=True,
            postgresql_where="legacy_response_log_id IS NOT NULL",
        ),
        Index("ix_llm_usage_events_occurred_at", "occurred_at"),
        Index("ix_llm_usage_events_agent_occurred", "agent_id", "occurred_at"),
        Index("ix_llm_usage_events_provider_model_occurred", "provider_key", "model_key", "occurred_at"),
        Index("ix_llm_usage_events_source_type_occurred", "source_type", "occurred_at"),
        Index("ix_llm_usage_events_conversation", "conversation_id"),
        Index(
            "ix_llm_usage_events_unpriced_created",
            "created_at",
            postgresql_where="cost_usd IS NULL AND is_deleted = 0",
        ),
        CheckConstraint(
            "source_type IN ('workflow', 'llm_analyst', 'evaluation')", name="ck_llm_usage_events_source_type"
        ),
        CheckConstraint(
            "pricing_status IN ('configured', 'fallback', 'unpriced', 'legacy_estimate')",
            name="ck_llm_usage_events_pricing_status",
        ),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0 AND call_index >= 0",
            name="ck_llm_usage_events_non_negative",
        ),
        CheckConstraint(
            "cache_read_tokens >= 0 AND cache_creation_tokens >= 0",
            name="ck_llm_usage_events_cache_tokens_non_negative",
        ),
        CheckConstraint("total_tokens >= input_tokens + output_tokens", name="ck_llm_usage_events_total_ge_parts"),
        CheckConstraint("prompt_tokens >= input_tokens", name="ck_llm_usage_events_prompt_ge_input"),
    )

    execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    call_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    workflow_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True
    )
    llm_provider_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True
    )
    llm_analyst_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("llm_analyst.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    node_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    legacy_response_log_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agent_response_logs.id", ondelete="SET NULL"), nullable=True
    )

    provider_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    token_details: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    cache_creation_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    prompt_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")

    input_per_1k: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)
    output_per_1k: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)
    cache_read_per_1k: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)
    cache_creation_per_1k: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)
    pricing_status: Mapped[str] = mapped_column(String(20), nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LlmUsageCaptureRunModel(Base):
    """One receipt per workflow or analyst run"""

    __tablename__ = "llm_usage_capture_runs"
    __table_args__ = (
        UniqueConstraint("execution_id", name="uq_llm_usage_capture_runs_execution"),
        Index("ix_llm_usage_capture_runs_occurred_at", "occurred_at"),
        Index("ix_llm_usage_capture_runs_source_occurred", "source", "occurred_at"),
        CheckConstraint(
            "source_type IN ('workflow', 'llm_analyst', 'evaluation')", name="ck_llm_usage_capture_runs_source_type"
        ),
        CheckConstraint("execution_outcome IN ('returned', 'raised')", name="ck_llm_usage_capture_runs_outcome"),
        CheckConstraint(
            "run_status IN ('completed', 'failed', 'paused', 'idle', 'running')",
            name="ck_llm_usage_capture_runs_run_status",
        ),
        CheckConstraint(
            "expected_entries >= 0 AND persisted_events >= 0", name="ck_llm_usage_capture_runs_non_negative"
        ),
    )

    execution_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    execution_outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    run_status: Mapped[str] = mapped_column(String(16), nullable=False)

    expected_entries: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    persisted_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    agent_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    workflow_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LlmUsageControlModel(Base):
    """Single shared control row for capture state (keyed by ``singleton_key``)"""

    __tablename__ = "llm_usage_control"
    __table_args__ = (UniqueConstraint("singleton_key", name="uq_llm_usage_control_singleton"),)

    singleton_key: Mapped[str] = mapped_column(String(32), nullable=False, default=CONTROL_SINGLETON_KEY)

    capture_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    capture_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )
