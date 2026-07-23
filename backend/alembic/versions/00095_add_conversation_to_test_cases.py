"""add_conversation_to_test_cases

Links each test case to the conversation it was imported from and its position
within that conversation, so evaluation runs can replay each conversation as an
isolated memory thread.

Both columns are nullable: legacy and manually created cases have no source
conversation and are treated as independent single-turn conversations.

Revision ID: 4e1c7a9d2b05
Revises: 322883fb3a4d
Create Date: 2026-07-20 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "4e1c7a9d2b05"
down_revision: Union[str, None] = "322883fb3a4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column("source_conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "test_cases",
        sa.Column("turn_index", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_test_cases_source_conversation_id",
        "test_cases",
        ["source_conversation_id"],
    )
    # Execution groups by conversation and orders by turn within it.
    op.create_index(
        "ix_test_cases_conversation_turn",
        "test_cases",
        ["suite_id", "source_conversation_id", "turn_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_test_cases_conversation_turn", table_name="test_cases")
    op.drop_index("ix_test_cases_source_conversation_id", table_name="test_cases")
    op.drop_column("test_cases", "turn_index")
    op.drop_column("test_cases", "source_conversation_id")
