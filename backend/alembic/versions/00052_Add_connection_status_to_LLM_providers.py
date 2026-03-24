"""Add connection status to LLM providers

Revision ID: 89d6a38dfd1c
Revises: c1d2e3f4a5b6
Create Date: 2026-03-18 22:32:15.865762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '89d6a38dfd1c'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INITIAL_STATUS = '{"status": "Untested", "last_tested_at": null, "message": null}'


def upgrade() -> None:
    op.add_column('llm_providers', sa.Column('connection_status', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=INITIAL_STATUS))
    op.execute(f"UPDATE llm_providers SET connection_status = '{INITIAL_STATUS}'::jsonb WHERE connection_status IS NULL")


def downgrade() -> None:
    op.drop_column('llm_providers', 'connection_status')
