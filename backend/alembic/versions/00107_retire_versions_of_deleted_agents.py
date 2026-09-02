"""retire versions of deleted agents

Revision ID: b8454171e700
Revises: db1cbdf682c5
Create Date: 2026-08-19 15:59:06.713081

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8454171e700'
down_revision: Union[str, None] = 'db1cbdf682c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE workflows w
        SET is_deleted = 1
        FROM agents a
        WHERE w.agent_id = a.id
          AND a.is_deleted = 1
          AND w.is_deleted = 0
        """
    )


def downgrade() -> None:
    pass
