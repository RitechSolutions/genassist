"""add agent response logs logged at index

Adds a partial index on ``agent_response_logs.logged_at`` covering non-deleted
rows. The conversations-with-activity query behind ``/analytics/agents/summary``
and the dashboard conversation count both filter that column, and it had no
index: every first load of the Agent Performance screen scanned the table's
whole history.

Revision ID: db1cbdf682c5
Revises: 639dcc861c9c
Create Date: 2026-08-13 14:00:29.457251

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "db1cbdf682c5"
down_revision: Union[str, None] = "639dcc861c9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_agent_response_logs_logged_at"
_TABLE = "agent_response_logs"


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
            ON {_TABLE} (logged_at)
            WHERE is_deleted = 0
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
