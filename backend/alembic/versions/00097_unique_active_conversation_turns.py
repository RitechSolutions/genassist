"""unique_active_conversation_turns

Guards against a conversation being imported twice into the same dataset, which
would produce duplicate turn positions and replay the conversation out of order.

Only active rows are constrained. Manual and legacy cases keep a null
source_conversation_id and are unaffected, since nulls never conflict.

Revision ID: c5d9e0a71b38
Revises: 8b2f5c31d740
Create Date: 2026-07-21 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "c5d9e0a71b38"
down_revision: Union[str, None] = "8b2f5c31d740"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX_NAME = "uq_test_cases_active_conversation_turn"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        "test_cases",
        ["suite_id", "source_conversation_id", "turn_index"],
        unique=True,
        postgresql_where="is_deleted = 0 AND source_conversation_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="test_cases")
