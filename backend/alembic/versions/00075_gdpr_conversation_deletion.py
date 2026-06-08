"""GDPR conversation deletion: pii_redacted_at column, GIN index, permission seed

Adds support for admin-driven Right-to-Erasure on conversations:
- ``conversations.pii_redacted_at`` timestamp marks rows whose PII has been
  scrubbed in-place (anonymize mode).
- Functional GIN index on ``custom_attributes -> 'pii' -> 'requester_email'``
  speeds up admin search-by-email lookups.
- Seeds ``delete:conversation:gdpr`` permission and grants it to the ``admin``
  role.

The change is purely additive; existing functionality (soft delete, internal
hard delete, conversation list/search) is preserved.

Revision ID: g7d8e9f0a1b2
Revises: f5e3ae54e989
Create Date: 2026-04-30 11:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "g7d8e9f0a1b2"
down_revision: Union[str, None] = "f5e3ae54e989"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GDPR_DELETE_PERMISSION_NAME = "delete:conversation:gdpr"
GDPR_DELETE_PERMISSION_DESCRIPTION = (
    "Allows admins to delete or anonymize a conversation for GDPR "
    "Right-to-Erasure requests."
)
ADMIN_ROLE_NAME = "admin"


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("pii_redacted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_conversations_pii_requester_email
        ON conversations
        USING gin ((custom_attributes -> 'pii' -> 'requester_email'))
        """
    )

    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO permissions (id, name, is_active, description, is_deleted, created_at, updated_at)
            VALUES (gen_random_uuid(), :name, 1, :description, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (name) DO NOTHING
            """
        ),
        {
            "name": GDPR_DELETE_PERMISSION_NAME,
            "description": GDPR_DELETE_PERMISSION_DESCRIPTION,
        },
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO role_permissions (id, role_id, permission_id, is_deleted, created_at, updated_at)
            SELECT gen_random_uuid(), r.id, p.id, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM roles r
            CROSS JOIN permissions p
            WHERE r.name = :role_name
              AND p.name = :permission_name
              AND NOT EXISTS (
                SELECT 1 FROM role_permissions rp
                WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
            """
        ),
        {
            "role_name": ADMIN_ROLE_NAME,
            "permission_name": GDPR_DELETE_PERMISSION_NAME,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE name = :permission_name
            )
            """
        ),
        {"permission_name": GDPR_DELETE_PERMISSION_NAME},
    )

    conn.execute(
        sa.text("DELETE FROM permissions WHERE name = :permission_name"),
        {"permission_name": GDPR_DELETE_PERMISSION_NAME},
    )

    op.execute("DROP INDEX IF EXISTS ix_conversations_pii_requester_email")

    op.drop_column("conversations", "pii_redacted_at")
