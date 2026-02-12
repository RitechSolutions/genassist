"""add audit_log modified_at index

Revision ID: a7c8d9e0f123
Revises: a1b2c3d4e5f6
Create Date: 2026-02-06

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7c8d9e0f123"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_log_modified_at",
        "audit_log",
        ["modified_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_modified_at", table_name="audit_log")
