"""add category to evaluations

Revision ID: ab9eb40b9978
Revises: c3a9d27e5b41
Create Date: 2026-11-03 10:25:18.442079

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ab9eb40b9978'
down_revision: Union[str, None] = 'c3a9d27e5b41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Databases that ran the merged 00125 already have it; checking first skips the table lock
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("test_evaluations")}
    if "category" not in columns:
        op.add_column("test_evaluations", sa.Column("category", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("test_evaluations", "category")
