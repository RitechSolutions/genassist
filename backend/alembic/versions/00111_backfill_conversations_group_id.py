"""backfill conversations group id

Revision ID: 454448e85877
Revises: d37941010920
Create Date: 2026-09-11 14:06:54.923591

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '454448e85877'
down_revision: Union[str, None] = 'd37941010920'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
            """
            UPDATE conversations c
            SET group_id = u.group_id
            FROM operators o
            JOIN agents a ON a.operator_id = o.id AND a.is_deleted = 0
            JOIN users u ON u.id = a.created_by AND u.is_deleted = 0
            WHERE c.operator_id = o.id
            AND c.group_id IS NULL
            AND u.group_id IS NOT NULL
            """
        )

def downgrade() -> None:
    pass
