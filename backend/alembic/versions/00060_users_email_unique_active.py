"""unique email among non-deleted users

Revision ID: e8f9a0b1c2d3
Revises: d7e3f1a2b8c5
Create Date: 2026-03-31 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e3f1a2b8c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "users_email_active_key",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index("users_email_active_key", table_name="users")
