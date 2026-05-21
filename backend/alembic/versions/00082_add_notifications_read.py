"""add user_notification_reads

Revision ID: 0684bdb56872
Revises: k1l2m3n4o5p6
Create Date: 2026-05-21 11:58:19.175589

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0684bdb56872"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_notification_reads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("notification_id", sa.String(length=255), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "notification_id",
            name="uq_user_notification_reads_user_notification",
        ),
    )
    op.create_index(
        op.f("ix_user_notification_reads_notification_id"),
        "user_notification_reads",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_notification_reads_user_id"),
        "user_notification_reads",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_notification_reads_user_id"),
        table_name="user_notification_reads",
    )
    op.drop_index(
        op.f("ix_user_notification_reads_notification_id"),
        table_name="user_notification_reads",
    )
    op.drop_table("user_notification_reads")
