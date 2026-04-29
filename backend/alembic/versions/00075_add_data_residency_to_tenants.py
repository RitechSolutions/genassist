"""add data_residency to tenants

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-29 00:00:00.000000

The tenants table only exists in the master database.
This migration is a no-op when applied to tenant databases.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5e3ae54e989"
down_revision: Union[str, None] = "4c12ea3c2660"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenants_table_exists(conn) -> bool:
    result = conn.execute(
        sa.text("SELECT to_regclass('public.tenants')")
    ).scalar()
    return result is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _tenants_table_exists(conn):
        return

    op.add_column(
        "tenants",
        sa.Column("data_residency", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not _tenants_table_exists(conn):
        return

    op.drop_column("tenants", "data_residency")