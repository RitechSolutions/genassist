"""reset analytics aggregation timestamp to trigger full recalculation

Revision ID: d1e2f3a4b5c6
Revises: ccaa77b2b8e3
Create Date: 2026-03-26 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "ccaa77b2b8e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reset last_aggregated_at to Jan 1, 2026 to trigger full recalculation
    # on the next Celery aggregation run
    op.execute(
        "UPDATE agent_execution_daily_stats SET last_aggregated_at = '2026-01-01 00:00:00+00'"
    )


def downgrade() -> None:
    # No-op: we can't restore the original timestamps
    pass
