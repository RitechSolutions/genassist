"""add analytics aggregation state

Adds the discovery infrastructure for the analytics aggregation: a
non-partial concurrent index on ``conversations.updated_at`` (discovery
deliberately includes soft-deleted conversations, so no ``WHERE is_deleted = 0``)
and the single-row ``analytics_aggregation_state`` cursor table.

Revision ID: cdb1de95f099
Revises: d37941010920
Create Date: 2026-08-31 20:47:14.287388

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "cdb1de95f099"
down_revision: Union[str, None] = "d37941010920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_conversations_updated_at"
_TABLE = "analytics_aggregation_state"


def upgrade() -> None:
    # Index first: autocommit_block commits the preceding transaction
    # unconditionally, so the table DDL below stays transactional.
    with op.get_context().autocommit_block():
        left_invalid = op.get_bind().scalar(
            sa.text("SELECT NOT indisvalid FROM pg_index WHERE indexrelid = to_regclass(:name)"),
            {"name": _INDEX},
        )
        if left_invalid:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")

        op.execute(
            f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {_INDEX}
            ON conversations (updated_at)
            """
        )

    op.create_table(
        _TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("state_key", sa.Integer(), nullable=False),
        sa.Column("last_incremental_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="analytics_aggregation_state_pk"),
        sa.UniqueConstraint("state_key", name="uq_analytics_aggregation_state_key"),
        sa.CheckConstraint("state_key = 1", name="ck_analytics_aggregation_state_key"),
    )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_INDEX}")
    op.drop_table(_TABLE)
