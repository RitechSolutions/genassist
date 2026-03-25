"""add_settings_and_llm_analyst_to_agent_and_conversation

Revision ID: c1d2e3f4a5b6
Revises: a7b8c9d0e1f2
Create Date: 2026-03-17 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("llm_analyst_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("finalize_llm_analyst_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "llm_analyst",
        sa.Column("settings", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "finalize_llm_analyst_id")
    op.drop_column("agents", "llm_analyst_id")
    op.drop_column("llm_analyst", "settings")