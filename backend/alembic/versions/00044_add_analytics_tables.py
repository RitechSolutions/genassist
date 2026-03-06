"""add_analytics_tables

Revision ID: f3c9e2b7a1d4
Revises: 410a77facee8
Create Date: 2026-03-04 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3c9e2b7a1d4"
down_revision: Union[str, None] = "8f9429646c9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### agent_execution_daily_stats ###
    op.create_table(
        "agent_execution_daily_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_response_ms", sa.Float(), nullable=True),
        sa.Column("min_response_ms", sa.Float(), nullable=True),
        sa.Column("max_response_ms", sa.Float(), nullable=True),
        sa.Column("total_response_ms", sa.Float(), nullable=True),
        sa.Column("total_nodes_executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_success_rate", sa.Float(), nullable=True),
        sa.Column("total_success_rate_sum", sa.Float(), nullable=True),
        sa.Column("rag_used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_conversations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finalized_conversations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("in_progress_conversations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("thumbs_up_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("thumbs_down_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_aggregated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id", "stat_date",
            name="uq_agent_execution_daily_stats_agent_date",
        ),
    )
    op.create_index(
        op.f("ix_agent_execution_daily_stats_agent_id"),
        "agent_execution_daily_stats",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_execution_daily_stats_stat_date"),
        "agent_execution_daily_stats",
        ["stat_date"],
        unique=False,
    )

    # ### node_execution_daily_stats ###
    op.create_table(
        "node_execution_daily_stats",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("node_type", sa.String(100), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_execution_ms", sa.Float(), nullable=True),
        sa.Column("min_execution_ms", sa.Float(), nullable=True),
        sa.Column("max_execution_ms", sa.Float(), nullable=True),
        sa.Column("total_execution_ms", sa.Float(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "agent_id", "node_type", "stat_date",
            name="uq_node_execution_daily_stats_agent_node_date",
        ),
    )
    op.create_index(
        op.f("ix_node_execution_daily_stats_agent_id"),
        "node_execution_daily_stats",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_node_execution_daily_stats_node_type"),
        "node_execution_daily_stats",
        ["node_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_node_execution_daily_stats_stat_date"),
        "node_execution_daily_stats",
        ["stat_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_node_execution_daily_stats_stat_date"),
        table_name="node_execution_daily_stats",
    )
    op.drop_index(
        op.f("ix_node_execution_daily_stats_node_type"),
        table_name="node_execution_daily_stats",
    )
    op.drop_index(
        op.f("ix_node_execution_daily_stats_agent_id"),
        table_name="node_execution_daily_stats",
    )
    op.drop_table("node_execution_daily_stats")

    op.drop_index(
        op.f("ix_agent_execution_daily_stats_stat_date"),
        table_name="agent_execution_daily_stats",
    )
    op.drop_index(
        op.f("ix_agent_execution_daily_stats_agent_id"),
        table_name="agent_execution_daily_stats",
    )
    op.drop_table("agent_execution_daily_stats")
