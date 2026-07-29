"""add llm usage ledger tables

Creates the ledger tables (events, receipts, control flag) and adds optional
``workflow_execution_id`` on ``agent_response_logs``.

Revision ID: c6974c08b567
Revises: b7c2e9d14a83
Create Date: 2026-07-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c6974c08b567"
down_revision: Union[str, None] = "b7c2e9d14a83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONTROL_SINGLETON_ID = "b6d0f631-a0ab-440c-87ab-7630cff691e1"


def _audit_timestamp_softdelete_columns() -> list[sa.Column]:
    return [
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default=sa.text("0")),
    ]


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("call_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=64), nullable=True),
        sa.Column("agent_id", sa.UUID(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workflow_id", sa.UUID(), sa.ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("llm_provider_id", sa.UUID(), sa.ForeignKey("llm_providers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("llm_analyst_id", sa.UUID(), sa.ForeignKey("llm_analyst.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_id", sa.String(length=128), nullable=True),
        sa.Column(
            "legacy_response_log_id",
            sa.UUID(),
            sa.ForeignKey("agent_response_logs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_key", sa.String(length=64), nullable=True),
        sa.Column("model_key", sa.String(length=512), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("token_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("input_per_1k", sa.Numeric(18, 10), nullable=True),
        sa.Column("output_per_1k", sa.Numeric(18, 10), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 10), nullable=True),
        sa.Column("pricing_status", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_timestamp_softdelete_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", "call_index", name="uq_llm_usage_events_execution_call"),
        sa.CheckConstraint("source_type IN ('workflow', 'llm_analyst')", name="ck_llm_usage_events_source_type"),
        sa.CheckConstraint(
            "pricing_status IN ('configured', 'fallback', 'unpriced', 'legacy_estimate')",
            name="ck_llm_usage_events_pricing_status",
        ),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0 AND call_index >= 0",
            name="ck_llm_usage_events_non_negative",
        ),
        sa.CheckConstraint("total_tokens >= input_tokens + output_tokens", name="ck_llm_usage_events_total_ge_parts"),
    )
    op.create_index("ix_llm_usage_events_occurred_at", "llm_usage_events", ["occurred_at"])
    op.create_index("ix_llm_usage_events_agent_occurred", "llm_usage_events", ["agent_id", "occurred_at"])
    op.create_index(
        "ix_llm_usage_events_provider_model_occurred",
        "llm_usage_events",
        ["provider_key", "model_key", "occurred_at"],
    )
    op.create_index("ix_llm_usage_events_source_type_occurred", "llm_usage_events", ["source_type", "occurred_at"])
    op.create_index("ix_llm_usage_events_conversation", "llm_usage_events", ["conversation_id"])
    op.create_index(
        "uq_llm_usage_events_legacy_log",
        "llm_usage_events",
        ["legacy_response_log_id"],
        unique=True,
        postgresql_where=sa.text("legacy_response_log_id IS NOT NULL"),
    )

    op.create_table(
        "llm_usage_capture_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("execution_outcome", sa.String(length=16), nullable=False),
        sa.Column("run_status", sa.String(length=16), nullable=False),
        sa.Column("expected_entries", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("persisted_events", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("agent_id", sa.UUID(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workflow_id", sa.UUID(), sa.ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        *_audit_timestamp_softdelete_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id", name="uq_llm_usage_capture_runs_execution"),
        sa.CheckConstraint("source_type IN ('workflow', 'llm_analyst')", name="ck_llm_usage_capture_runs_source_type"),
        sa.CheckConstraint("execution_outcome IN ('returned', 'raised')", name="ck_llm_usage_capture_runs_outcome"),
        sa.CheckConstraint(
            "run_status IN ('completed', 'failed', 'paused', 'idle', 'running')",
            name="ck_llm_usage_capture_runs_run_status",
        ),
        sa.CheckConstraint(
            "expected_entries >= 0 AND persisted_events >= 0", name="ck_llm_usage_capture_runs_non_negative"
        ),
    )
    op.create_index("ix_llm_usage_capture_runs_occurred_at", "llm_usage_capture_runs", ["occurred_at"])
    op.create_index("ix_llm_usage_capture_runs_source_occurred", "llm_usage_capture_runs", ["source", "occurred_at"])

    op.create_table(
        "llm_usage_control",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("singleton_key", sa.String(length=32), nullable=False),
        sa.Column("capture_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("capture_started_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        *_audit_timestamp_softdelete_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_key", name="uq_llm_usage_control_singleton"),
    )
    op.execute(
        sa.text(
            "INSERT INTO llm_usage_control "
            "(id, singleton_key, capture_enabled, capture_started_at, is_deleted) "
            "VALUES (:id, 'singleton', true, now(), 0) "
            "ON CONFLICT (singleton_key) DO NOTHING"
        ).bindparams(id=_CONTROL_SINGLETON_ID)
    )

    # Correlation key: response logs ↔ workflow executions (additive, nullable)
    op.add_column("agent_response_logs", sa.Column("workflow_execution_id", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_agent_response_logs_workflow_execution_id",
        "agent_response_logs",
        ["workflow_execution_id"],
        unique=True,
        postgresql_where=sa.text("workflow_execution_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_response_logs_workflow_execution_id", table_name="agent_response_logs")
    op.drop_column("agent_response_logs", "workflow_execution_id")

    op.drop_table("llm_usage_control")

    op.drop_index("ix_llm_usage_capture_runs_source_occurred", table_name="llm_usage_capture_runs")
    op.drop_index("ix_llm_usage_capture_runs_occurred_at", table_name="llm_usage_capture_runs")
    op.drop_table("llm_usage_capture_runs")

    op.drop_index("uq_llm_usage_events_legacy_log", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_conversation", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_source_type_occurred", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_provider_model_occurred", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_agent_occurred", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_occurred_at", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
