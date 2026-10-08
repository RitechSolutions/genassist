"""add issue workflow fields and subtopic

Revision ID: 835357fc69d8
Revises: c263cbb56ca5
Create Date: 2026-10-06 09:19:26.680620
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "835357fc69d8"
down_revision: Union[str, None] = "c263cbb56ca5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_STATUSES = [
    ("open", "Open", "todo", 0, "amber"),
    ("in_progress", "In Progress", "in_progress", 1, "blue"),
    ("needs_help_desk_fix", "Needs Help Desk Fix", "in_progress", 2, "purple"),
    ("qa_approved", "QA Approved", "in_progress", 3, "teal"),
    ("resolved", "Resolved", "done", 4, "emerald"),
    ("wont_fix", "Won't Fix", "done", 5, "zinc"),
]


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("is_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("message_issues", sa.Column("fix_version", sa.String(length=100), nullable=True))
    op.add_column("message_issues", sa.Column("target_rollout_date", sa.Date(), nullable=True))
    op.add_column("conversation_analysis", sa.Column("subtopic", sa.String(length=255), nullable=True))
    op.create_index(
        "ix_conversation_analysis_topic_subtopic", "conversation_analysis", ["topic", "subtopic", "is_deleted"]
    )

    op.create_table(
        "issue_statuses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("color", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Integer(), server_default="1", nullable=False),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_issue_statuses_key"),
    )
    for key, label, category, position, color in SEED_STATUSES:
        op.execute(
            sa.text(
                "INSERT INTO issue_statuses (id, key, label, category, position, color, is_active, is_deleted) "
                "VALUES (gen_random_uuid(), :key, :label, :category, :position, :color, 1, 0)"
            ).bindparams(key=key, label=label, category=category, position=position, color=color)
        )

    op.create_table(
        "message_issue_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_feedback_id", sa.UUID(), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["message_feedback_id"], ["message_feedback.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_issue_notes_message_feedback_id", "message_issue_notes", ["message_feedback_id"])


def downgrade() -> None:
    op.drop_index("ix_message_issue_notes_message_feedback_id", table_name="message_issue_notes")
    op.drop_table("message_issue_notes")
    op.drop_table("issue_statuses")
    op.drop_index("ix_conversation_analysis_topic_subtopic", table_name="conversation_analysis")
    op.drop_column("conversation_analysis", "subtopic")
    op.drop_column("message_issues", "target_rollout_date")
    op.drop_column("message_issues", "fix_version")
