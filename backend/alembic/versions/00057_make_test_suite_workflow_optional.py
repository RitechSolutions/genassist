"""make_test_suite_workflow_optional

Revision ID: f14f0d39c2ab
Revises: e9e20304a429
Create Date: 2026-03-13 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f14f0d39c2ab"
down_revision: Union[str, None] = "e9e20304a429"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pylint: disable=no-member
    op.alter_column(
        "test_suites",
        "workflow_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    # pylint: disable=no-member
    op.alter_column(
        "test_suites",
        "workflow_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

