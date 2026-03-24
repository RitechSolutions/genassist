"""add_execution_trace_to_test_results

Revision ID: c3a1d2b4f9aa
Revises: f14f0d39c2ab
Create Date: 2026-03-13 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c3a1d2b4f9aa"
down_revision: Union[str, None] = "f14f0d39c2ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pylint: disable=no-member
    op.add_column(
        "test_results",
        sa.Column(
            "execution_trace",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # pylint: disable=no-member
    op.drop_column("test_results", "execution_trace")
