"""add_greet_on_start_to_agents

Adds agent-level "greet on conversation start" settings: a boolean toggle and an
optional greeting-prompt extension (appended to the built-in default greeting prompt).

Revision ID: a3b4c5d6e7f8
Revises: 9f1df080dab5
Create Date: 2026-06-30 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "9f1df080dab5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "greet_on_start",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "agents",
        sa.Column("greeting_prompt", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "greeting_prompt")
    op.drop_column("agents", "greet_on_start")
