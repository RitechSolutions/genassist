"""add evaluation checks feature flag

Seeds ``evaluations.checks`` hidden. It shows the one-page evaluation editor with
Should / Should not checks, and the Results, Checks and Settings tabs.

Revision ID: a416df487c31
Revises: 9a409e53648c
Create Date: 2026-10-09 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a416df487c31"
down_revision: Union[str, None] = "9a409e53648c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_FLAG_KEY = "evaluations.checks"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO feature_flags (id, key, val, description, is_active, is_deleted)
        VALUES (gen_random_uuid(), '{FEATURE_FLAG_KEY}', 'false',
                'Evaluation checks (one-page editor with Should and Should not checks)', 1, 0)
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM feature_flags WHERE key = '{FEATURE_FLAG_KEY}'")
