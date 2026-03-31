"""unique email on users (all rows, including soft-deleted)

Enforces a single unique index on email across all rows, including soft-deleted,
so the same address cannot exist on both an active and a deleted user.

Revision ID: e8f9a0b1c2d3
Revises: d7e3f1a2b8c5
Create Date: 2026-03-31 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e3f1a2b8c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_users_email",
        "users",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_email", table_name="users")
