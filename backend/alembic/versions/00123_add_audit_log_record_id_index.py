"""add audit log record id index

Revision ID: 6afdf3640e70
Revises: a416df487c31
Create Date: 2026-10-13 08:03:50.807205

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "6afdf3640e70"
down_revision: Union[str, None] = "a416df487c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_audit_log_record_id_table_name"
_TABLE = "audit_log"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        left_invalid = op.get_bind().scalar(
            sa.text("SELECT NOT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)"),
            {"name": _INDEX},
        )
        if left_invalid:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")

        op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX} ON {_TABLE} (record_id, table_name)")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
