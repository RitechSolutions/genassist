"""add custom_attributes JSONB column to conversations

Stores workflow dynamic parameters (e.g. region, tier) as queryable
JSONB on each conversation so they can be filtered and used in analytics.

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-04-03 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("custom_attributes", JSONB, nullable=True),
    )
    op.create_index(
        "ix_conversations_custom_attributes_gin",
        "conversations",
        ["custom_attributes"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_custom_attributes_gin", table_name="conversations")
    op.drop_column("conversations", "custom_attributes")
