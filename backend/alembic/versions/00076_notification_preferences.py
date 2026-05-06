"""notification preferences

Revision ID: 1a8d7aaeb61e
Revises: g7d8e9f0a1b2
Create Date: 2026-05-06 09:38:32.253829
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1a8d7aaeb61e"
down_revision: Union[str, None] = "g7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_notification_preferences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("workflow_failed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_tenant_notification_preferences_tenant_id"),
        "tenant_notification_preferences",
        ["tenant_id"],
        unique=True,
    )

    op.create_table(
        "user_notification_preferences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_started", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("conversation_hostility", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("conversation_finalized_hostility", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_user_notification_preferences_user_id"),
        "user_notification_preferences",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_notification_preferences_user_id"),
        table_name="user_notification_preferences",
    )
    op.drop_table("user_notification_preferences")

    op.drop_index(
        op.f("ix_tenant_notification_preferences_tenant_id"),
        table_name="tenant_notification_preferences",
    )
    op.drop_table("tenant_notification_preferences")
