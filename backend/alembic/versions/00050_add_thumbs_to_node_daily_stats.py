"""add_thumbs_to_node_daily_stats

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-03-10 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "node_execution_daily_stats",
        sa.Column("thumbs_up_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "node_execution_daily_stats",
        sa.Column("thumbs_down_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("node_execution_daily_stats", "thumbs_down_count")
    op.drop_column("node_execution_daily_stats", "thumbs_up_count")
