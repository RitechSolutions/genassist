"""add unpriced created index

Adds a partial index on ``llm_usage_events.created_at`` covering only unpriced,
non-deleted rows. It serves the newest-unpriced watermark the Cost Explorer uses
to decide whether a dismissed pricing-coverage notice should return: because the
index holds nothing else, the watermark is a first-row lookup rather than a scan
past every priced call recorded since.

Built with CREATE INDEX CONCURRENTLY so no write lock is taken on
``llm_usage_events`` (written on every LLM call) while the index is built.
CONCURRENTLY cannot run inside a transaction, so this uses an autocommit block
the same way migration 00091 does.

Revision ID: 5161ef5ad5de
Revises: a5784baf5f4c
Create Date: 2026-07-31 15:20:24.542929

"""

from typing import Sequence, Union

from alembic import op

revision: str = "5161ef5ad5de"
down_revision: Union[str, None] = "a5784baf5f4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_llm_usage_events_unpriced_created"
_TABLE = "llm_usage_events"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX}
            ON {_TABLE} (created_at)
            WHERE cost_usd IS NULL AND is_deleted = 0
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
