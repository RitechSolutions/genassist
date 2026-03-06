"""Add connection_status to data sources

Revision ID: 8f9429646c9a
Revises: 410a77facee8
Create Date: 2026-03-05 11:32:10.416397

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8f9429646c9a'
down_revision: Union[str, None] = '410a77facee8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INITIAL_STATUS = '{"status": "Untested", "last_tested_at": null, "message": null}'


def upgrade() -> None:
    op.add_column(
        'data_sources',
        sa.Column(
            'connection_status',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=INITIAL_STATUS,
        ),
    )
    op.execute(
        f"UPDATE data_sources SET connection_status = '{INITIAL_STATUS}'::jsonb WHERE connection_status IS NULL"
    )


def downgrade() -> None:
    op.drop_column('data_sources', 'connection_status')
