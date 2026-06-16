"""add_azure_work_items_reports

Revision ID: c2bce7366f69
Revises: 5d4d7a65f44b
Create Date: 2026-06-15 16:10:03.163069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2bce7366f69"
down_revision: Union[str, None] = "5d4d7a65f44b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("reporter_user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("repro_steps", sa.Text(), nullable=True),
        sa.Column("system_info", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
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
        sa.Column("vote_count", sa.Integer(), nullable=False),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["app_settings_id"], ["app_settings.id"]),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["support_tickets.id"]),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_support_tickets_azure_work_item_id"),
        "support_tickets",
        ["azure_work_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_duplicate_of_id"),
        "support_tickets",
        ["duplicate_of_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_fingerprint"),
        "support_tickets",
        ["fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_reporter_user_id"),
        "support_tickets",
        ["reporter_user_id"],
        unique=False,
    )

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
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

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
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ticket_sync_outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("ticket_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
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
        sa.Column("is_deleted", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticket_id", "operation", name="uq_ticket_sync_outbox_ticket_op"
        ),
    )


def downgrade() -> None:
    op.drop_table("ticket_sync_outbox")
    op.drop_table("support_ticket_events")
    op.drop_table("support_ticket_comments")

    op.drop_index(op.f("ix_support_tickets_reporter_user_id"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_fingerprint"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_duplicate_of_id"), table_name="support_tickets")
    op.drop_index(
        op.f("ix_support_tickets_azure_work_item_id"), table_name="support_tickets"
    )
    op.drop_table("support_tickets")
