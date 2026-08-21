"""add technique to test_tool_rule_results

Rule results are no longer Tool Usage only: Route Taken and Action Taken rules are
graded per scope too. Existing rows all came from Tool Usage.

Revision ID: c41d7ab35f92
Revises: b8454171e700
Create Date: 2026-08-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c41d7ab35f92"
down_revision: Union[str, None] = "b8454171e700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_tool_rule_results",
        sa.Column(
            "technique",
            sa.String(length=64),
            nullable=False,
            server_default="tool_used",
        ),
    )


def downgrade() -> None:
    op.drop_column("test_tool_rule_results", "technique")
