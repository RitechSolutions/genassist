"""remove target_variable from ml_models

Revision ID: d1e2f3a4b5c6
Revises: 410a77facee8
Create Date: 2026-02-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "410a77facee8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("ml_models", "target_variable")


def downgrade() -> None:
    op.add_column(
        "ml_models",
        sa.Column("target_variable", sa.String(255), nullable=True),
    )
