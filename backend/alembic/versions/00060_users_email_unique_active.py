"""unique email on users (all rows, including soft-deleted)

Enforces a single unique index on email across all rows, including soft-deleted,
so the same address cannot exist on both an active and a deleted user.

Revision ID: e8f9a0b1c2d3
Revises: d7e3f1a2b8c5
Create Date: 2026-03-31 12:00:00.000000

"""

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e3f1a2b8c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EMAIL_RE = re.compile(r"^(.+)@(.+)$")


def _split_email(email: str) -> tuple[str, str] | None:
    m = _EMAIL_RE.match(email.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def _dedupe_user_emails(connection) -> None:
    """
    Before creating a unique index on users.email, rename duplicate rows so each
    address is unique: first row per email unchanged, others get local+1@domain,
    local+2@domain, ... skipping any address already taken.
    """
    dup_rows = connection.execute(
        sa.text("""
            SELECT email
            FROM users
            WHERE email IS NOT NULL AND TRIM(email) <> ''
            GROUP BY email
            HAVING COUNT(*) > 1
        """)
    ).fetchall()

    for (email,) in dup_rows:
        parts = _split_email(email)
        if parts is None:
            local, domain = "user", "invalid.local"
        else:
            local, domain = parts

        user_rows = connection.execute(
            sa.text("SELECT id FROM users WHERE email = :email ORDER BY id"),
            {"email": email},
        ).fetchall()

        for i, row in enumerate(user_rows[1:], start=1):
            suffix = i
            while True:
                new_email = f"{local}+{suffix}@{domain}"
                taken = connection.execute(
                    sa.text("SELECT 1 FROM users WHERE email = :e LIMIT 1"),
                    {"e": new_email},
                ).fetchone()
                if not taken:
                    break
                suffix += 1
            connection.execute(
                sa.text("UPDATE users SET email = :new WHERE id = :id"),
                {"new": new_email, "id": row.id},
            )


def upgrade() -> None:
    # Rename duplicate emails so each address is unique: first row per email unchanged, others get local+1@domain,
    # local+2@domain, ... skipping any address already taken.
    connection = op.get_bind()
    _dedupe_user_emails(connection)

    op.create_index(
        "users_email_unique",
        "users",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("users_email_unique", table_name="users")
