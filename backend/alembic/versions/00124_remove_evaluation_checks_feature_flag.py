"""remove evaluation checks feature flag

Revision ID: 82e8726df1a0
Revises: 6afdf3640e70
Create Date: 2026-10-19 14:16:51.767468

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '82e8726df1a0'
down_revision: Union[str, None] = '6afdf3640e70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FEATURE_FLAG_KEY = "evaluations.checks"


def upgrade() -> None:
    op.execute(f"DELETE FROM feature_flags WHERE key = '{FEATURE_FLAG_KEY}'")


def downgrade() -> None:
    op.execute(f"""
               INSERT INTO feature_flags (id, key, val, description, is_active, is_deleted)
               VALUES (gen_random_uuid(), '{FEATURE_FLAG_KEY}', 'false',
               'Evaluation checks (one-page editor with Should and Should not checks)', 1, 0)
               ON CONFLICT (key) DO NOTHING
               """)
