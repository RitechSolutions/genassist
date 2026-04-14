"""api key rotation overlap + optional credential expiry

Combines optional previous-hash overlap (rotation) and optional credential
lifetime (`credential_expires_at` / `expires_in_days` on create).

Revision ID: b3c4d5e6f7a8
Revises: 30f4c089509b
Create Date: 2026-04-14 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "30f4c089509b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("previous_hashed_value", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "api_keys",
        sa.Column(
            "previous_hashed_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "api_keys",
        sa.Column(
            "credential_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "credential_expires_at")
    op.drop_column("api_keys", "previous_hashed_expires_at")
    op.drop_column("api_keys", "previous_hashed_value")
