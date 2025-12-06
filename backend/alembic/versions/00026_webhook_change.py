"""webhook_change

Revision ID: b9e655051a61
Revises: da094ae2244c
Create Date: 2025-11-05 15:49:50.748883

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b9e655051a61"
down_revision: Union[str, None] = "da094ae2244c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing webhooks table completely
    op.drop_table("webhooks")

    # Recreate the webhooks table with the new clean structure
    op.create_table(
        "webhooks",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("secret", sa.String(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "webhook_type", sa.String(), nullable=False, server_default="generic"
        ),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("app_settings_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], name="webhooks_agent_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["app_settings_id"],
            ["app_settings.id"],
            name="webhooks_app_settings_id_fkey",
        ),
        sa.UniqueConstraint("name", name="webhooks_name_key"),
    )
    op.create_index("ix_webhooks_name", "webhooks", ["name"], unique=False)


def downgrade() -> None:
    # Drop the existing webhooks table completely
    op.drop_table("webhooks")

    # Recreate the webhooks table with the old structure (before migration)
    op.create_table(
        "webhooks",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("secret", sa.String(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], name="webhooks_workflow_id_fkey"
        ),
        sa.UniqueConstraint("name", name="webhooks_name_key"),
    )
    op.create_index("ix_webhooks_name", "webhooks", ["name"], unique=False)
