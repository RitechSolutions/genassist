"""The bootstrap seed must not drift from migration 00054's bedrock rows: fresh
databases are stamped at head and skip data migrations, so seeding is the only way
they receive the region-specific Bedrock rates an upgraded database already has"""

import importlib.util
from decimal import Decimal
from pathlib import Path

_MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "00054_add_llm_cost_rates_table.py"


def _migration_bedrock_rows() -> set:
    spec = importlib.util.spec_from_file_location("parity_00054", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {
        (provider, model, Decimal(str(input_per_1k)), Decimal(str(output_per_1k)))
        for provider, model, input_per_1k, output_per_1k in module._SEED_ROWS
        if provider == "bedrock"
    }


def test_the_bootstrap_rows_match_the_migration_seed():
    from app.db.seed.llm_cost_rates import BEDROCK_SEED_COST_RATES

    seeded = {
        (provider, model, Decimal(input_per_1k), Decimal(output_per_1k))
        for provider, model, input_per_1k, output_per_1k in BEDROCK_SEED_COST_RATES
    }

    assert seeded == _migration_bedrock_rows()
