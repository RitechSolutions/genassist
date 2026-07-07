"""add_notifications

Revision ID: e9d128a0e7f1
Revises: i9f0a1b2c3d4
Create Date: 2026-05-13 14:58:36.972766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e9d128a0e7f1"
down_revision: Union[str, None] = "i9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("is_tenant", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("allow_all_tenant_users", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_types_type"),
        "notification_types",
        ["type"],
        unique=True,
    )

    op.create_table(
        "notification_type_recipient_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("notification_type_id", sa.UUID(), nullable=False),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["user_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["notification_type_id"], ["notification_types.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_type_id",
            "group_id",
            name="uq_nt_recipient_groups_type_group",
        ),
    )
    op.create_index(
        op.f("ix_notification_type_recipient_groups_group_id"),
        "notification_type_recipient_groups",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_type_recipient_groups_notification_type_id"),
        "notification_type_recipient_groups",
        ["notification_type_id"],
        unique=False,
    )

    op.create_table(
        "notification_type_recipient_users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("notification_type_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["notification_type_id"], ["notification_types.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_type_id",
            "user_id",
            name="uq_nt_recipient_users_type_user",
        ),
    )
    op.create_index(
        op.f("ix_notification_type_recipient_users_notification_type_id"),
        "notification_type_recipient_users",
        ["notification_type_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_type_recipient_users_user_id"),
        "notification_type_recipient_users",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "user_notification_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("notification_type_id", sa.UUID(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["notification_type_id"], ["notification_types.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "notification_type_id",
            name="uq_user_notification_settings_user_type",
        ),
    )
    op.create_index(
        op.f("ix_user_notification_settings_notification_type_id"),
        "user_notification_settings",
        ["notification_type_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_notification_settings_user_id"),
        "user_notification_settings",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_notification_settings_user_id"),
        table_name="user_notification_settings",
    )
    op.drop_index(
        op.f("ix_user_notification_settings_notification_type_id"),
        table_name="user_notification_settings",
    )
    op.drop_table("user_notification_settings")

    op.drop_index(
        op.f("ix_notification_type_recipient_users_user_id"),
        table_name="notification_type_recipient_users",
    )
    op.drop_index(
        op.f("ix_notification_type_recipient_users_notification_type_id"),
        table_name="notification_type_recipient_users",
    )
    op.drop_table("notification_type_recipient_users")

    op.drop_index(
        op.f("ix_notification_type_recipient_groups_notification_type_id"),
        table_name="notification_type_recipient_groups",
    )
    op.drop_index(
        op.f("ix_notification_type_recipient_groups_group_id"),
        table_name="notification_type_recipient_groups",
    )
    op.drop_table("notification_type_recipient_groups")

    op.drop_index(op.f("ix_notification_types_type"), table_name="notification_types")
    op.drop_table("notification_types")
