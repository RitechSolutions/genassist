"""add category to datasets

Revision ID: a601f9fbdddb
Revises: 8fe3986c2a43
Create Date: 2026-10-20 14:29:59.862657

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a601f9fbdddb'
down_revision: Union[str, None] = '8fe3986c2a43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_suites", sa.Column("category", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("test_suites", "category")
