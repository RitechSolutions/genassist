"""Add audio_providers table

Revision ID: h8e9f1a2b3c4
Revises: g7d8e9f0a1b2
Create Date: 2026-05-07 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "h8e9f1a2b3c4"
down_revision: Union[str, None] = "g7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audio_providers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("provider_type", sa.String(length=50), nullable=True),
        sa.Column("capability", sa.String(length=10), nullable=True),
        sa.Column("connection_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("connection_status", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("is_default", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audio_providers")
