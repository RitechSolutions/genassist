"""Add audio_data and audio_format to transcript_messages

Revision ID: i9f0a1b2c3d4
Revises: h8e9f1a2b3c4
Create Date: 2026-05-08 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "i9f0a1b2c3d4"
down_revision: Union[str, None] = "h8e9f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("transcript_messages", sa.Column("audio_data", sa.LargeBinary(), nullable=True))
    op.add_column("transcript_messages", sa.Column("audio_format", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("transcript_messages", "audio_format")
    op.drop_column("transcript_messages", "audio_data")
