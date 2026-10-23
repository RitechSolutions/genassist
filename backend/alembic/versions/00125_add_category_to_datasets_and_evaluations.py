"""add category to datasets and evaluations

Revision ID: a601f9fbdddb
Revises: 82e8726df1a0
Create Date: 2026-10-20 14:29:59.862657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a601f9fbdddb'
down_revision: Union[str, None] = '82e8726df1a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_suites", sa.Column("category", sa.String(length=50), nullable=True))
    op.add_column("test_evaluations", sa.Column("category", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("test_evaluations", "category")
    op.drop_column("test_suites", "category")
