"""Bootstrap rows for llm_cost_rates.

Bedrock ships no static fallback rates (AWS bills a geographic profile at its
source Region's rate), so fresh databases, stamped at head, never running the
00054 data migration, must receive the region-specific rows through seeding.
"""

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.llm_cost_rate import LlmCostRateModel

# (provider_key, model_key, input_per_1k, output_per_1k)
BEDROCK_SEED_COST_RATES: tuple[tuple[str, str, str, str], ...] = (
    ("bedrock", "eu.amazon.nova-2-lite-v1:0", "0.0001", "0.0004"),
    ("bedrock", "ca.amazon.nova-2-lite-v1:0", "0.0001", "0.0004"),
    ("bedrock", "us.amazon.nova-2-lite-v1:0", "0.0001", "0.0004"),
    ("bedrock", "us.amazon.nova-2-pro-v1:0", "0.0002", "0.0008"),
    ("bedrock", "us.amazon.nova-2-flash-v1:0", "0.0004", "0.0016"),
)


async def seed_llm_cost_rates(session: AsyncSession) -> None:
    """Insert missing rows only: an existing active row for the same provider/model wins"""
    await session.execute(
        pg_insert(LlmCostRateModel)
        .values(
            [
                {
                    "provider_key": provider,
                    "model_key": model,
                    "input_per_1k": Decimal(input_per_1k),
                    "output_per_1k": Decimal(output_per_1k),
                }
                for provider, model, input_per_1k, output_per_1k in BEDROCK_SEED_COST_RATES
            ]
        )
        .on_conflict_do_nothing(
            index_elements=["provider_key", "model_key"],
            index_where=text("is_deleted = 0"),
        )
    )
    await session.commit()
