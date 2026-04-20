"""add_is_system_to_agents

Revision ID: f1a2b3c4d5e6
Revises: pe0069a1b2c3
Create Date: 2026-04-20 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "pe0069a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_AGENT_NAMES = (
    "Support Assistant",
    "Support Assistant for genassist",
    "Workflow Builder",
)


def upgrade() -> None:
    # 1. Add the column with a default of false
    op.add_column(
        "agents",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # 2. Mark the three seeded agents as system agents
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE agents SET is_system = true "
            "WHERE name IN :names AND is_deleted = 0"
        ),
        {"names": SYSTEM_AGENT_NAMES},
    )


def downgrade() -> None:
    op.drop_column("agents", "is_system")
