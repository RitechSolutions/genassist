"""add group_id to conversations for group-scoped dashboard and notifications

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-05-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("group_id", sa.UUID(), nullable=True),
        if_not_exists=True,
    )
    op.create_foreign_key(
        "fk_conversations_group_id",
        "conversations",
        "user_groups",
        ["group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_conversations_group_id",
        "conversations",
        ["group_id"],
        if_not_exists=True,
    )

    # Backfill from agent owner's user group (matches ConversationRepository.save_conversation).
    op.execute(
        """
        UPDATE conversations c
        SET group_id = u.group_id
        FROM operators o
        JOIN agents a ON a.operator_id = o.id AND a.is_deleted = 0
        JOIN users u ON u.id = a.created_by AND u.is_deleted = 0
        WHERE c.operator_id = o.id
          AND c.group_id IS NULL
          AND u.group_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_group_id", table_name="conversations", if_exists=True)
    op.drop_constraint("fk_conversations_group_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "group_id", if_exists=True)
