"""add llm usage fallback created index

Adds a partial index on ``llm_usage_events.created_at`` covering only
fallback-priced, non-deleted rows. It serves the newest-fallback watermark the
Cost Explorer uses to decide whether a dismissed fallback-rates notice should
return, so the lookup stays a first-row read however the rows are distributed.

Revision ID: 8b64f74cbf09
Revises: 8f3c2a91b7d4
Create Date: 2026-09-23 20:19:20.567981

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8b64f74cbf09"
down_revision: Union[str, None] = "8f3c2a91b7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_llm_usage_events_fallback_created"
_TABLE = "llm_usage_events"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        left_invalid = op.get_bind().scalar(
            sa.text("SELECT NOT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)"),
            {"name": _INDEX},
        )
        if left_invalid:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")

        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX}
            ON {_TABLE} (created_at)
            WHERE pricing_status = 'fallback' AND is_deleted = 0
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
