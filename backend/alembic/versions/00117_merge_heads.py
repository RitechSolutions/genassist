"""merge heads

Revision ID: 3ef08a6d2676
Revises: 0af5effac072, e1a2b3c4d5f6
Create Date: 2026-09-30 12:14:03.194679

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ef08a6d2676'
down_revision: Union[str, None] = ('0af5effac072', 'e1a2b3c4d5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
