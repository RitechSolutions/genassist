"""add full-text search tsvector column to transcript_messages

Adds a GENERATED ALWAYS STORED tsvector column and GIN index for
fast full-text search across conversation messages.

Revision ID: f7e2b1c3d4a5
Revises: c4b8a0d2e9f1
Create Date: 2026-04-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7e2b1c3d4a5"
down_revision: Union[str, None] = "c4b8a0d2e9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add generated tsvector column — auto-populates for all existing rows
    op.execute(
        """
        ALTER TABLE transcript_messages
        ADD COLUMN text_search tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED
        """
    )
    # GIN index for fast full-text lookups
    op.execute(
        """
        CREATE INDEX ix_transcript_messages_text_search
        ON transcript_messages USING gin (text_search)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcript_messages_text_search")
    op.execute("ALTER TABLE transcript_messages DROP COLUMN IF EXISTS text_search")
