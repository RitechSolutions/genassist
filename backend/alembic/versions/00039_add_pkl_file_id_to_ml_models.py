"""add pkl_file_id to ml_models

Revision ID: b8d9e0f12345
Revises: a7c8d9e0f123
Create Date: 2026-02-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8d9e0f12345"
down_revision: Union[str, None] = "a7c8d9e0f123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ml_models", sa.Column("pkl_file_id", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("ml_models", "pkl_file_id")
