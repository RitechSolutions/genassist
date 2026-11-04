"""add category to evaluations

Revision ID: 8fe3986c2a43
Revises: 82e8726df1a0
Create Date: 2026-10-30 16:49:06.919347

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8fe3986c2a43'
down_revision: Union[str, None] = '82e8726df1a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_evaluations", sa.Column("category", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("test_evaluations", "category")
