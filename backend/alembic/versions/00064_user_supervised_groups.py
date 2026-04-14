"""user_supervised_groups junction table

Revision ID: b2c3d4e5f6a7
Revises: 04f81f9dbfd8
Create Date: 2026-04-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "30f4c089509b"
down_revision: Union[str, None] = "04f81f9dbfd8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_supervised_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["user_groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "group_id", name="uq_user_supervised_group"),
    )
    op.create_index("ix_user_supervised_groups_user_id", "user_supervised_groups", ["user_id"])
    op.create_index("ix_user_supervised_groups_group_id", "user_supervised_groups", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_user_supervised_groups_group_id", table_name="user_supervised_groups")
    op.drop_index("ix_user_supervised_groups_user_id", table_name="user_supervised_groups")
    op.drop_table("user_supervised_groups")