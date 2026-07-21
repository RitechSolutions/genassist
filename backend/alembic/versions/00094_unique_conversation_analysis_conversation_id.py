"""unique_conversation_analysis_conversation_id

Enforce one analysis row per conversation.

A conversation could previously accumulate multiple ``conversation_analysis``
rows because every write went through a plain INSERT with no DB uniqueness
(migration 00091 added only a *non-unique* index on ``conversation_id``). This
migration:
  1. de-duplicates existing rows, keeping the most recent analysis per
     conversation (by ``created_at``, then ``id``),
  2. drops the now-superseded non-unique index, and
  3. adds a UNIQUE constraint on ``conversation_id`` so re-analysis can only
     replace the existing row, never add another.

Revision ID: 3900c6b0aaeb
Revises: 21f612ab93ba
Create Date: 2026-07-21 13:59:24.226385

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3900c6b0aaeb'
down_revision: Union[str, None] = '21f612ab93ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNIQUE_CONSTRAINT = "uq_conversation_analysis_conversation_id"
NON_UNIQUE_INDEX = "ix_conversation_analysis_conversation_id"


def upgrade() -> None:
    # (1) Collapse duplicate analysis rows to one per conversation, keeping the
    #     most recent. Without this the UNIQUE constraint below would fail.
    op.execute(
        """
        DELETE FROM conversation_analysis ca
        USING (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY conversation_id
                       ORDER BY created_at DESC NULLS LAST, id DESC
                   ) AS rn
            FROM conversation_analysis
        ) dups
        WHERE ca.id = dups.id
          AND dups.rn > 1
        """
    )

    # (2) The non-unique index is superseded by the unique constraint's index.
    op.execute(f"DROP INDEX IF EXISTS {NON_UNIQUE_INDEX}")

    # (3) Enforce the one-analysis-per-conversation invariant at the DB level.
    op.create_unique_constraint(
        UNIQUE_CONSTRAINT, "conversation_analysis", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        UNIQUE_CONSTRAINT, "conversation_analysis", type_="unique"
    )
    # Recreate the plain b-tree index that migration 00091 relied on.
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {NON_UNIQUE_INDEX}
        ON conversation_analysis (conversation_id)
        """
    )