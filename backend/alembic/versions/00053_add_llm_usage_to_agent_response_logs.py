"""add_llm_usage_to_agent_response_logs_and_stats

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-03-17 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, None] = "89d6a38dfd1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # agent_response_logs
    op.add_column(
        "agent_response_logs",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_response_logs",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_response_logs",
        sa.Column("total_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_response_logs",
        sa.Column("cost_usd", sa.Float(), nullable=True),
    )

    # agent_execution_daily_stats
    op.add_column(
        "agent_execution_daily_stats",
        sa.Column("total_input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_execution_daily_stats",
        sa.Column("total_output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "agent_execution_daily_stats",
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_response_logs", "cost_usd")
    op.drop_column("agent_response_logs", "total_tokens")
    op.drop_column("agent_response_logs", "output_tokens")
    op.drop_column("agent_response_logs", "input_tokens")

    op.drop_column("agent_execution_daily_stats", "total_cost_usd")
    op.drop_column("agent_execution_daily_stats", "total_output_tokens")
    op.drop_column("agent_execution_daily_stats", "total_input_tokens")
