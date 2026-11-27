"""add trigram index on conversation summary for search

Skipped with a warning when pg_trgm is not available to the migration role.

Revision ID: 9a763f065641
Revises: f1376a542c32
Create Date: 2026-11-27 13:57:06.000000

"""

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError

from alembic import op

revision: str = "9a763f065641"
down_revision: Union[str, None] = "f1376a542c32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

_INDEX = "ix_conversation_analysis_summary_trgm"
_TARGET = "conversation_analysis USING gin (summary gin_trgm_ops)"


def _trigram_usable() -> bool:
    query = "SELECT 1 FROM pg_opclass WHERE opcname = 'gin_trgm_ops' AND pg_opclass_is_visible(oid)"
    return bool(op.get_bind().scalar(sa.text(query)))


def _try_create_trigram_extension() -> None:
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except DBAPIError as error:
        logger.warning("Could not create the pg_trgm extension: %s", error.orig)


def _build_in_progress() -> bool:
    # Joined on pg_locks: other roles' progress rows hide index_relid but not pid.
    query = """
        SELECT 1 FROM pg_stat_progress_create_index AS progress
        JOIN pg_locks AS lock ON lock.pid = progress.pid
        WHERE lock.relation = to_regclass(:name)
        LIMIT 1
    """
    return bool(op.get_bind().scalar(sa.text(query), {"name": _INDEX}))


def _drop_invalid_leftover() -> None:
    left_invalid = op.get_bind().scalar(
        sa.text("SELECT NOT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)"),
        {"name": _INDEX},
    )
    if left_invalid:
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        if not _trigram_usable():
            _try_create_trigram_extension()

        if not _trigram_usable():
            logger.warning("pg_trgm is not available; skipping %s", _INDEX)
            return

        if _build_in_progress():
            logger.warning("%s is still being built by another session; leaving it to finish", _INDEX)
            return

        _drop_invalid_leftover()
        op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX} ON {_TARGET}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
