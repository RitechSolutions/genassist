"""add trained by to ML models

Records which workflow and Train Model node trained a model, so a copied
workflow with the same node id and model name no longer updates it.

Revision ID: bc71d6b34aec
Revises: 242b618b4766
Create Date: 2026-11-15 16:28:49.730638
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bc71d6b34aec"
down_revision: Union[str, None] = "242b618b4766"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ml_models", sa.Column("trained_by_workflow_id", sa.UUID(), nullable=True))
    op.add_column("ml_models", sa.Column("trained_by_node_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ml_models", "trained_by_node_id")
    op.drop_column("ml_models", "trained_by_workflow_id")
