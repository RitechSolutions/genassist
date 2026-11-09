"""add training metrics to ML models

Stores the validation metrics produced by the Train Model node on the model
registry row. Evaluate can then display and rank models trained outside an ML
Model Pipeline, while promotion can replace the values with a selected run's
metrics.

Revision ID: d8f31a6b902e
Revises: c3a9d27e5b41
Create Date: 2026-11-04 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d8f31a6b902e"
down_revision: Union[str, None] = "c3a9d27e5b41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ml_models",
        sa.Column(
            "training_metrics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("ml_models", "training_metrics")
