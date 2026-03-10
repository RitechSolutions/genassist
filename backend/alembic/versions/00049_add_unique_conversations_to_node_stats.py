"""add_unique_conversations_to_node_stats

Revision ID: a7b8c9d0e1f2
Revises: f3c9e2b7a1d4
Create Date: 2026-03-10 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f3c9e2b7a1d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "node_execution_daily_stats",
        sa.Column("unique_conversations", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("node_execution_daily_stats", "unique_conversations")
