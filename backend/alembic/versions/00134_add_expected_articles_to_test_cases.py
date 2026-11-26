"""add expected_articles to test_cases

The articles the knowledge search should find on a turn, each by title or id.
Existing rows keep none.

Revision ID: 2434847a42e8
Revises: f1376a542c32
Create Date: 2026-11-21 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2434847a42e8"
down_revision: Union[str, None] = "f1376a542c32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_cases",
        sa.Column("expected_articles", postgresql.JSONB(), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("test_cases", "expected_articles")
