"""add indexes to speed up conversation search/filter

Targets the slow conversation search queries (topic/summary ILIKE, correlated
EXISTS on conversation_analysis, ORDER BY created_at DESC pagination).

Adds:
- b-tree index on conversation_analysis.conversation_id (FK had no index -> the
  correlated EXISTS subquery was doing a seq scan per conversation row)
- pg_trgm GIN indexes on conversations.topic and conversation_analysis.summary so
  leading-wildcard ILIKE '%x%' can use an index instead of a seq scan
- partial b-tree on conversations.created_at DESC (live rows) for ORDER BY + LIMIT

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
    # Try to enable pg_trgm (needed by the gin_trgm_ops operator class used by
    # the topic/summary indexes). In some environments the migration role lacks
    # CREATE privilege on the database, so this can fail. We tolerate that and
    # simply skip the trigram indexes rather than blocking the whole migration:
    # the critical FK/ordering indexes below don't depend on pg_trgm.
    bind = op.get_bind()

    def _trgm_installed() -> bool:
        return bool(
            bind.exec_driver_sql(
                "SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"
            ).scalar()
        )

    trgm_available = _trgm_installed()
    if not trgm_available:
        # Attempt to create it inside a SAVEPOINT so a permission failure only
        # rolls back this nested block and leaves the migration transaction
        # usable (a raw failed statement would otherwise poison the whole txn).
        try:
            with bind.begin_nested():
                op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            trgm_available = _trgm_installed()
        except Exception:
            trgm_available = False
    if not trgm_available:
        print(
            "WARNING: pg_trgm extension is not installed and could not be "
            "created; skipping trigram indexes (ix_conversations_topic_trgm, "
            "ix_conversation_analysis_summary_trgm). Install pg_trgm and "
            "create these indexes manually to speed up ILIKE searches."
        )

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

        # (2) Trigram indexes so ILIKE '%term%' is index-backed.
        #     Only buildable when pg_trgm is present.
        if trgm_available:
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                    ix_conversations_topic_trgm
                ON conversations USING gin (topic gin_trgm_ops)
                """
            )
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                    ix_conversation_analysis_summary_trgm
                ON conversation_analysis USING gin (summary gin_trgm_ops)
                """
            )

        # (3) Support ORDER BY created_at DESC + pagination for live rows.
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
            "DROP INDEX CONCURRENTLY IF EXISTS ix_conversation_analysis_summary_trgm"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_conversations_topic_trgm"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_conversation_analysis_conversation_id"
        )
    # Leave the pg_trgm extension in place; other objects may depend on it.
