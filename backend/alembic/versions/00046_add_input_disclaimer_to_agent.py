"""add input disclaimer to agent

Revision ID: 00044_disclaimer
Revises: bbf0dbf460f4
Create Date: 2026-03-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "00044_disclaimer"
down_revision: Union[str, None] = "bbf0dbf460f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("input_disclaimer", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("input_disclaimer_link_url", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("input_disclaimer_link_label", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "input_disclaimer_link_label")
    op.drop_column("agents", "input_disclaimer_link_url")
    op.drop_column("agents", "input_disclaimer")
