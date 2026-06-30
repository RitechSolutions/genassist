"""add prompt_versions and prompt_configs tables

Revision ID: pe0069a1b2c3
Revises: a9d1c4e2b7f0
Create Date: 2026-04-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "pe0069a1b2c3"
down_revision: Union[str, None] = "a9d1c4e2b7f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("node_id", sa.String(100), nullable=False),
        sa.Column("prompt_field", sa.String(50), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "node_id", "prompt_field", "version_number",
            name="uq_prompt_version_context",
        ),
    )
    op.create_index(
        "ix_prompt_versions_context",
        "prompt_versions",
        ["workflow_id", "node_id", "prompt_field"],
    )

    op.create_table(
        "prompt_configs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("node_id", sa.String(100), nullable=False),
        sa.Column("prompt_field", sa.String(50), nullable=False),
        sa.Column("gold_suite_id", sa.UUID(), sa.ForeignKey("test_suites.id"), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "node_id", "prompt_field",
            name="uq_prompt_config_context",
        ),
    )


def downgrade() -> None:
    op.drop_table("prompt_configs")
    op.drop_index("ix_prompt_versions_context", table_name="prompt_versions")
    op.drop_table("prompt_versions")
