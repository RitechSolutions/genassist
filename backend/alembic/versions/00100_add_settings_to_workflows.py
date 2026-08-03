"""add_settings_to_workflows

Adds a nullable JSONB ``settings`` column to the ``workflows`` table holding
per-workflow editor/UI preferences (currently the node rendering style, e.g.
``{"nodeStyle": "compact"}``).

Nullable with no backfill: existing workflows have no stored preference and fall
back to the default ("detailed") node rendering at the application layer.

Revision ID: a3f9c1d7e204
Revises: d4b1f2a3c5e6
Create Date: 2026-07-23 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3f9c1d7e204"
down_revision: Union[str, None] = "d4b1f2a3c5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workflows", "settings")
