"""add_status_to_test_results

Records why a case did or did not produce metrics, so skipped cases, execution
failures and scoring failures can be told apart instead of all reading as
"no metrics".

Legacy rows that carry metrics are marked scored. Legacy rows without metrics
keep a null status: the stored data cannot prove whether they were skipped,
execution failures or scoring failures, and the reader treats null as unscored.

Revision ID: e7a4b0c95d61
Revises: c5d9e0a71b38
Create Date: 2026-07-21 16:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a4b0c95d61"
down_revision: Union[str, None] = "c5d9e0a71b38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_results",
        sa.Column("status", sa.String(32), nullable=True),
    )
    # Only rows holding real metrics can be proven to have scored.
    op.execute(
        """
        UPDATE test_results
        SET status = 'scored'
        WHERE metrics IS NOT NULL
          AND jsonb_typeof(metrics) = 'object'
          AND metrics <> '{}'::jsonb
        """
    )


def downgrade() -> None:
    op.drop_column("test_results", "status")
