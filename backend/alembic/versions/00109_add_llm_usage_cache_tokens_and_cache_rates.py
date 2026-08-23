"""add llm usage cache tokens and cache rates

The four rate columns are nullable because NULL and ``0`` are distinct states the
pricing formula reads differently. On ``llm_cost_rates`` NULL means "not configured"
— a provider default applies — while an explicit ``0`` means "free" (Amazon Nova
cache writes, for one). On ``llm_usage_events`` the snapshots stay NULL for calls
with no cache activity, and otherwise record the effective per-1K rates actually
used, so ``cost_usd`` is reproducible from the row alone.

``downgrade`` checks both tables before dropping columns. Cache data on an
event would make ``cost_usd`` impossible to reconstruct, so that refusal is
absolute. Configured rates can be exported and recreated, so that error says
how. ``<> 0`` also blocks negative counts. The guard reads rows,
so ``alembic downgrade --sql`` cannot render this migration.

Revision ID: d37941010920
Revises: c41d7ab35f92
Create Date: 2026-08-19 11:36:40.419380

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d37941010920"
down_revision: Union[str, None] = "c41d7ab35f92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EVENTS = "llm_usage_events"
_RATES = "llm_cost_rates"


def upgrade() -> None:
    op.add_column(
        _EVENTS, sa.Column("cache_read_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0"))
    )
    op.add_column(
        _EVENTS, sa.Column("cache_creation_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0"))
    )
    op.add_column(_EVENTS, sa.Column("cache_read_per_1k", sa.Numeric(18, 10), nullable=True))
    op.add_column(_EVENTS, sa.Column("cache_creation_per_1k", sa.Numeric(18, 10), nullable=True))

    op.add_column(_RATES, sa.Column("cache_read_per_1k", sa.Numeric(18, 10), nullable=True))
    op.add_column(_RATES, sa.Column("cache_creation_per_1k", sa.Numeric(18, 10), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()

    events = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {_EVENTS}"
            " WHERE cache_read_tokens <> 0 OR cache_creation_tokens <> 0"
            " OR cache_read_per_1k IS NOT NULL OR cache_creation_per_1k IS NOT NULL"
        )
    ).scalar_one()
    if events:
        raise RuntimeError(
            f"Refusing downgrade: {events} {_EVENTS} row(s) carry cache token counts or rate"
            " snapshots; dropping these columns would make their cost_usd non-reproducible."
        )

    rates = bind.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {_RATES}"
            " WHERE cache_read_per_1k IS NOT NULL OR cache_creation_per_1k IS NOT NULL"
        )
    ).scalar_one()
    if rates:
        raise RuntimeError(
            f"Refusing downgrade: {rates} {_RATES} row(s) have configured cache rates."
            " Export them to CSV, clear the cache columns, and retry."
        )

    op.drop_column(_RATES, "cache_creation_per_1k")
    op.drop_column(_RATES, "cache_read_per_1k")

    op.drop_column(_EVENTS, "cache_creation_per_1k")
    op.drop_column(_EVENTS, "cache_read_per_1k")
    op.drop_column(_EVENTS, "cache_creation_tokens")
    op.drop_column(_EVENTS, "cache_read_tokens")
