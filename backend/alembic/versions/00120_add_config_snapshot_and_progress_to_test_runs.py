"""add config snapshot and progress to test runs

Revision ID: 9a409e53648c
Revises: c263cbb56ca5
Create Date: 2026-10-09 09:57:16.500058

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9a409e53648c'
down_revision: Union[str, None] = 'c263cbb56ca5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("config_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column("test_runs", sa.Column("progress", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("test_runs", "progress")
    op.drop_column("test_runs", "config_snapshot")
