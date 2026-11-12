"""add last_successful_sync to knowledge_bases

last_synced moves on every sync run, also a failed one, because it schedules the
next run. last_successful_sync only moves when a run succeeds, so a knowledge base
whose syncs keep failing no longer looks freshly synced.

Existing rows whose last run succeeded get last_synced as their last successful
sync. Rows without a sync status (S3, SharePoint) stay empty until their next
successful run.

Revision ID: 3f8d2a6c1e94
Revises: 9c4e1f7a2b6d
Create Date: 2026-11-11 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3f8d2a6c1e94"
down_revision: Union[str, None] = "9c4e1f7a2b6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column("last_successful_sync", sa.DateTime(timezone=True), nullable=True),
        if_not_exists=True,
    )
    op.execute(
        "UPDATE knowledge_bases SET last_successful_sync = last_synced "
        "WHERE last_successful_sync IS NULL AND last_synced IS NOT NULL "
        "AND last_sync_status IN ('success', 'success_with_warnings')"
    )


def downgrade() -> None:
    op.drop_column("knowledge_bases", "last_successful_sync")
