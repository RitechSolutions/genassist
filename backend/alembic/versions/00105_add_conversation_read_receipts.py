"""add conversation read receipts

Creates ``conversation_read_receipts`` — a per-reader high-water mark of the last
message sequence a participant has seen in a conversation. One row per
``(conversation_id, reader_role)``: the visitor ("customer") on the chat widget
and the human "supervisor" on the agent console after a takeover. The AI agent is
never recorded as a reader.

A message is "seen by role R" when its ``sequence_number`` is ``<=`` that role's
``last_read_sequence``. This powers Sent / Delivered / Seen receipts in the chat
widget and the supervisor console. Modelled on ``user_notifications`` (the only
prior read-state table), but keyed at conversation granularity with a monotonic
sequence marker rather than a row per message.

Revision ID: 639dcc861c9c
Revises: 5161ef5ad5de
Create Date: 2026-08-12 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "639dcc861c9c"
down_revision: Union[str, None] = "5161ef5ad5de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "conversation_read_receipts"
_INDEX = "ix_conversation_read_receipts_conversation_id"
_UNIQUE = "uq_conversation_read_receipts_conversation_role"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("reader_role", sa.String(length=20), nullable=False),
        sa.Column("reader_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "last_read_sequence",
            sa.Integer(),
            server_default=sa.text("-1"),
            nullable=False,
        ),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column(
            "is_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "reader_role", name=_UNIQUE),
    )
    op.create_index(
        op.f(_INDEX), _TABLE, ["conversation_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f(_INDEX), table_name=_TABLE)
    op.drop_table(_TABLE)
