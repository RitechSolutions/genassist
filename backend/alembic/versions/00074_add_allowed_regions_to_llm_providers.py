"""add allowed_regions to llm_providers

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-04-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "4c12ea3c2660"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_providers",
        sa.Column("allowed_regions", JSONB, nullable=True),
    )

    # Backfill Bedrock providers: wrap their stored region_name (or the
    # default ca-central-1) into a single-element JSON array.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE llm_providers
            SET allowed_regions = jsonb_build_array(
                COALESCE(connection_data->>'region_name', 'ca-central-1')
            )
            WHERE llm_model_provider = 'bedrock'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("llm_providers", "allowed_regions")