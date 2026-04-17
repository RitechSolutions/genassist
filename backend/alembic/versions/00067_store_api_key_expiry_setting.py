"""store api key expiry setting

Adds `credential_expiry_days` to persist the selected expiration option (Never/30/90/180/365).
Rotation can then recompute `credential_expires_at` as now + stored days.

Revision ID: c4b8a0d2e9f1
Revises: b1a3ac1f5fe2
Create Date: 2026-04-14 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4b8a0d2e9f1"
down_revision: Union[str, None] = "b1a3ac1f5fe2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("credential_expiry_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "credential_expiry_days")

