"""add test_tool_rule_results table

Canonical per-rule outcomes for Tool Usage evaluation. Turn-scoped rules store
case_id; conversation-scoped rules store source_conversation_id. ``details`` holds
a snapshot of the evaluated rule so results stay readable after config changes.

Revision ID: b7c2e9d14a83
Revises: a3f9c1d7e204
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c2e9d14a83"
down_revision: Union[str, None] = "a3f9c1d7e204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_tool_rule_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=True),
        sa.Column("source_conversation_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["test_runs.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["test_cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_tool_rule_results_run", "test_tool_rule_results", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_test_tool_rule_results_run", table_name="test_tool_rule_results")
    op.drop_table("test_tool_rule_results")
