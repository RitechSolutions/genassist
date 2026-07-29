"""add indexes to speed up conversation search/filter

Targets the slow conversation search queries (correlated EXISTS on
conversation_analysis, ORDER BY created_at DESC pagination).

Adds:
- b-tree index on conversation_analysis.conversation_id (FK had no index -> the
  correlated EXISTS subquery was doing a seq scan per conversation row)
- partial b-tree on conversations.created_at DESC (live rows) for ORDER BY + LIMIT

Note: topic/summary ILIKE '%x%' searches are intentionally NOT indexed here.
A leading-wildcard ILIKE can only be index-backed via a pg_trgm GIN index, and
creating that extension requires CREATE privilege on the database which is not
available in all (e.g. managed prod) environments. Those searches continue to
run as sequential scans.

All indexes are built with CREATE INDEX CONCURRENTLY so no write locks are taken
on prod tables. CONCURRENTLY cannot run inside a transaction, so we use an
autocommit block (Alembic wraps each migration in a transaction by default).

Revision ID: d7f3a9c1e8b2
Revises: 66c71887a6da
Create Date: 2026-07-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f3a9c1e8b2"
down_revision: Union[str, None] = "66c71887a6da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY must run outside a transaction.
    with op.get_context().autocommit_block():
        # (1) Critical: index the FK column the correlated EXISTS subquery uses.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_conversation_analysis_conversation_id
            ON conversation_analysis (conversation_id)
            """
        )

        # (2) Support ORDER BY created_at DESC + pagination for live rows.
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_conversations_created_at_desc
            ON conversations (created_at DESC)
            WHERE is_deleted = 0
            """
        )


def downgrade() -> None:
    # DROP INDEX CONCURRENTLY also cannot run inside a transaction.
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_conversations_created_at_desc"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_conversation_analysis_conversation_id"
        )
