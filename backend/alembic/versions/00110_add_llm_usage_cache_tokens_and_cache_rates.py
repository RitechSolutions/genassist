"""add llm usage cache tokens and cache rates

The rate columns are nullable because NULL and 0 are distinct states: NULL
means "not configured" while an explicit 0 means "free".

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
_CACHE_TOKENS_CHECK = "ck_llm_usage_events_cache_tokens_non_negative"
_PROMPT_GE_INPUT_CHECK = "ck_llm_usage_events_prompt_ge_input"


def upgrade() -> None:
    op.add_column(
        _EVENTS, sa.Column("cache_read_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0"))
    )
    op.add_column(
        _EVENTS, sa.Column("cache_creation_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0"))
    )
    op.create_check_constraint(_CACHE_TOKENS_CHECK, _EVENTS, "cache_read_tokens >= 0 AND cache_creation_tokens >= 0")
    op.add_column(_EVENTS, sa.Column("cache_read_per_1k", sa.Numeric(18, 10), nullable=True))
    op.add_column(_EVENTS, sa.Column("cache_creation_per_1k", sa.Numeric(18, 10), nullable=True))

    op.add_column(_EVENTS, sa.Column("prompt_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")))
    op.execute(f"UPDATE {_EVENTS} SET prompt_tokens = input_tokens")
    op.create_check_constraint(_PROMPT_GE_INPUT_CHECK, _EVENTS, "prompt_tokens >= input_tokens")

    op.add_column(_RATES, sa.Column("cache_read_per_1k", sa.Numeric(18, 10), nullable=True))
    op.add_column(_RATES, sa.Column("cache_creation_per_1k", sa.Numeric(18, 10), nullable=True))


def downgrade() -> None:
    op.drop_column(_RATES, "cache_creation_per_1k")
    op.drop_column(_RATES, "cache_read_per_1k")

    op.drop_constraint(_PROMPT_GE_INPUT_CHECK, _EVENTS, type_="check")
    op.drop_column(_EVENTS, "prompt_tokens")

    op.drop_column(_EVENTS, "cache_creation_per_1k")
    op.drop_column(_EVENTS, "cache_read_per_1k")
    op.drop_constraint(_CACHE_TOKENS_CHECK, _EVENTS, type_="check")
    op.drop_column(_EVENTS, "cache_creation_tokens")
    op.drop_column(_EVENTS, "cache_read_tokens")
