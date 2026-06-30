"""Add fallback_chains table

Reusable, named ordered lists of LLM providers (with a retry policy) that workflow
LLM/Agent nodes can reference for automatic provider failover.

Revision ID: c4d5e6f7a8b9
Revises: 9f1df080dab5
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "66c71887a6da"
down_revision: Union[str, None] = "9f1df080dab5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fallback_chains",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("provider_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("retry_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("fallback_chains")
