"""user_groups table and group_id on users

Revision ID: a1b2c3d4e5f6
Revises: f1c2d3e4a5b6
Create Date: 2026-04-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "04f81f9dbfd8"
down_revision: Union[str, None] = "f1c2d3e4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "users",
        sa.Column("group_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_group_id",
        "users",
        "user_groups",
        ["group_id"],
        ["id"],
    )
    op.create_index("ix_users_group_id", "users", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_users_group_id", table_name="users")
    op.drop_constraint("fk_users_group_id", "users", type_="foreignkey")
    op.drop_column("users", "group_id")
    op.drop_table("user_groups")