"""support tickets and azure devops sync tables

Revision ID: m2n3o4p5q6r7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m2n3o4p5q6r7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_APP_SETTINGS_OLD = (
    "('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', "
    "'FileManagerSettings', 'Other', 'Security')"
)
_APP_SETTINGS_NEW = (
    "('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', "
    "'FileManagerSettings', 'Other', 'Security', 'AzureDevOps')"
)


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reporter_user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ticket_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("environment", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("azure_work_item_id", sa.Integer(), nullable=True),
        sa.Column("azure_project", sa.String(length=255), nullable=True),
        sa.Column("azure_url", sa.String(length=1024), nullable=True),
        sa.Column("app_settings_id", sa.UUID(), nullable=True),
        sa.Column("duplicate_of_id", sa.UUID(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("vote_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["app_settings_id"], ["app_settings.id"]),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["support_tickets.id"]),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_tickets_reporter_user_id", "support_tickets", ["reporter_user_id"])
    op.create_index("ix_support_tickets_fingerprint", "support_tickets", ["fingerprint"])
    op.create_index("ix_support_tickets_azure_work_item_id", "support_tickets", ["azure_work_item_id"])
    op.create_index("ix_support_tickets_duplicate_of_id", "support_tickets", ["duplicate_of_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])

    op.create_table(
        "support_ticket_comments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_ticket_comments_ticket_id", "support_ticket_comments", ["ticket_id"])

    op.create_table(
        "support_ticket_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_ticket_events_ticket_id", "support_ticket_events", ["ticket_id"])

    op.create_table(
        "ticket_sync_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "operation", name="uq_ticket_sync_outbox_ticket_op"),
    )
    op.create_index("ix_ticket_sync_outbox_status", "ticket_sync_outbox", ["status"])

    op.drop_constraint("app_settings_type_check", "app_settings", type_="check")
    op.create_check_constraint(
        "app_settings_type_check",
        "app_settings",
        f"type IN {_APP_SETTINGS_NEW}",
    )


def downgrade() -> None:
    op.drop_constraint("app_settings_type_check", "app_settings", type_="check")
    op.create_check_constraint(
        "app_settings_type_check",
        "app_settings",
        f"type IN {_APP_SETTINGS_OLD}",
    )
    op.execute("DELETE FROM app_settings WHERE type = 'AzureDevOps'")

    op.drop_index("ix_ticket_sync_outbox_status", table_name="ticket_sync_outbox")
    op.drop_table("ticket_sync_outbox")
    op.drop_index("ix_support_ticket_events_ticket_id", table_name="support_ticket_events")
    op.drop_table("support_ticket_events")
    op.drop_index("ix_support_ticket_comments_ticket_id", table_name="support_ticket_comments")
    op.drop_table("support_ticket_comments")
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_duplicate_of_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_azure_work_item_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_fingerprint", table_name="support_tickets")
    op.drop_index("ix_support_tickets_reporter_user_id", table_name="support_tickets")
    op.drop_table("support_tickets")
