"""add entra_oid for Microsoft SSO user mapping

Revision ID: j0k1l2m3n4o5
Revises: e9d128a0e7f1
Create Date: 2026-05-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "e9d128a0e7f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("entra_oid", sa.String(64), nullable=True),
        if_not_exists=True,
    )
    op.create_index(
        "uq_users_entra_oid_active",
        "users",
        ["entra_oid"],
        unique=True,
        postgresql_where=sa.text("entra_oid IS NOT NULL AND is_deleted = 0"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_entra_oid_active", table_name="users", if_exists=True)
    op.drop_column("users", "entra_oid", if_exists=True)
