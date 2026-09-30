"""add analysis attempts to conversations

Revision ID: c263cbb56ca5
Revises: 3c9d1e7a5b2f
Create Date: 2026-09-30 06:48:01.524482
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c263cbb56ca5"
down_revision: Union[str, None] = "3c9d1e7a5b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("analysis_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("conversations", sa.Column("analysis_last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("analysis_last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "analysis_last_error")
    op.drop_column("conversations", "analysis_last_attempt_at")
    op.drop_column("conversations", "analysis_attempts")
