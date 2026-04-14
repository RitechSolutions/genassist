"""api key rotation overlap + optional credential expiry

Combines optional previous-hash overlap (rotation) and optional credential
lifetime (`credential_expires_at` / `expires_in_days` on create).

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-11 12:00:00.000000

If your database was stamped with revision ``c4d5e6f7a8b9`` from the removed
follow-up migration, update ``alembic_version`` to ``b3c4d5e6f7a8`` (this
revision) once—schema is unchanged from that two-step sequence.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
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
