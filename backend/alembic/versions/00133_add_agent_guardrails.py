"""add agent guardrails

Revision ID: f1376a542c32
Revises: bc71d6b34aec
Create Date: 2026-11-17 12:45:40.705992

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1376a542c32'
down_revision: Union[str, None] = 'bc71d6b34aec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_security_settings",
        sa.Column("guardrails", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_table(
        "guardrail_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("transcript_message_id", sa.UUID(), nullable=True),
        sa.Column("workflow_execution_id", sa.String(length=64), nullable=True),
        sa.Column("stage", sa.String(length=16), nullable=False),
        sa.Column("check_type", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("detector", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=True),
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
        sa.Column("is_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_guardrail_events_agent_id_created_at", "guardrail_events", ["agent_id", "created_at"]
    )
    op.create_index("ix_guardrail_events_conversation_id", "guardrail_events", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("guardrail_events")
    op.drop_column("agent_security_settings", "guardrails")
