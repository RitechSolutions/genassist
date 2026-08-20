"""Unit tests for LLM cost rate CSV import/export"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

import app.services.llm_cost_rates as rate_module
from app.db.models.llm_cost_rate import LlmCostRateModel
from app.services.llm_cost_rates import LlmCostRateService


class FakeDb:
    def __init__(self, fail_commit: bool = False):
        self.added: list = []
        self.committed = False
        self.rolled_back = False
        self._fail_commit = fail_commit

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        if self._fail_commit:
            raise IntegrityError("insert", {}, Exception("duplicate key"))
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeRateRepo:
    def __init__(self, existing: dict | None = None, fail_commit: bool = False):
        self._existing = existing or {}
        self.db = FakeDb(fail_commit=fail_commit)
        self._listed: list = []

    async def get_active_by_provider_model(self, provider, model):
        return self._existing.get((provider, model))

    async def list_active(self):
        return self._listed


@pytest.fixture(autouse=True)
def _configure_mappers(app_def):
    return app_def


@pytest.fixture(autouse=True)
def _no_cache_calls(monkeypatch):
    monkeypatch.setattr(rate_module, "invalidate_llm_cost_rates_cache", lambda tenant=None: None)
    monkeypatch.setattr(rate_module, "get_tenant_context", lambda: "tenant-1")


def _row(provider, model, inp, outp, cache_read=None, cache_creation=None):
    return LlmCostRateModel(
        id=uuid4(),
        provider_key=provider,
        model_key=model,
        input_per_1k=inp,
        output_per_1k=outp,
        cache_read_per_1k=cache_read,
        cache_creation_per_1k=cache_creation,
        updated_at=datetime.now(timezone.utc),
    )


HEADER = "provider,model,input_per_1k,output_per_1k\n"
CACHE_HEADER = "provider,model,input_per_1k,output_per_1k,cache_read_per_1k,cache_creation_per_1k\n"


@pytest.mark.asyncio
async def test_import_inserts_normalized_rows_with_exact_decimals():
    repo = FakeRateRepo()
    service = LlmCostRateService(repo)

    result = await service.import_csv(HEADER + "  OpenAI , GPT-4o ,0.00015,0.0000001\n")

    assert (result.inserted, result.updated, result.errors) == (1, 0, [])
    added = repo.db.added[0]
    assert added.provider_key == "openai" and added.model_key == "gpt-4o"
    assert added.input_per_1k == Decimal("0.00015")
    assert added.output_per_1k == Decimal("0.0000001")
    assert repo.db.committed is True


@pytest.mark.asyncio
async def test_import_updates_existing_rate():
    existing = _row("openai", "gpt-4o", Decimal("0.001"), Decimal("0.002"))
    service = LlmCostRateService(FakeRateRepo(existing={("openai", "gpt-4o"): existing}))

    result = await service.import_csv(HEADER + "openai,gpt-4o,0.009,0.02\n")

    assert (result.inserted, result.updated) == (0, 1)
    assert existing.input_per_1k == Decimal("0.009")
    assert existing.output_per_1k == Decimal("0.02")


@pytest.mark.asyncio
async def test_import_reports_in_file_duplicate_and_keeps_first_row():
    repo = FakeRateRepo()
    service = LlmCostRateService(repo)

    result = await service.import_csv(HEADER + "openai,gpt-4o,0.001,0.002\nOPENAI, GPT-4o ,0.5,0.6\n")

    assert result.inserted == 1
    assert len(result.errors) == 1
    assert "duplicate of row 2" in result.errors[0]
    assert repo.db.added[0].input_per_1k == Decimal("0.001")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_row",
    [
        "openai,,0.001,0.002",
        ",gpt-4o,0.001,0.002",
        "   ,gpt-4o,0.001,0.002",
        "openai,gpt-4o,,0.002",
        "openai,gpt-4o,abc,0.002",
        "openai,gpt-4o,-0.001,0.002",
        "openai,gpt-4o,NaN,0.002",
        "openai,gpt-4o,0.001,Infinity",
    ],
)
async def test_import_rejects_bad_rows_without_dropping_good_ones(bad_row):
    repo = FakeRateRepo()
    service = LlmCostRateService(repo)

    result = await service.import_csv(HEADER + bad_row + "\nanthropic,claude-3-opus,0.015,0.075\n")

    assert result.inserted == 1
    assert len(result.errors) == 1
    assert result.errors[0].startswith("Row 2:")
    assert repo.db.added[0].provider_key == "anthropic"


@pytest.mark.asyncio
async def test_import_is_atomic_when_the_commit_conflicts():
    repo = FakeRateRepo(fail_commit=True)
    service = LlmCostRateService(repo)

    result = await service.import_csv(HEADER + "openai,gpt-4o,0.001,0.002\n")

    assert (result.inserted, result.updated) == (0, 0)
    assert repo.db.rolled_back is True
    assert any("No rows were imported" in e for e in result.errors)


@pytest.mark.asyncio
async def test_import_requires_header_columns():
    service = LlmCostRateService(FakeRateRepo())

    assert (await service.import_csv("")).errors == ["CSV has no header row"]
    missing = await service.import_csv("provider,model\nopenai,gpt-4o\n")
    assert missing.errors == ["Missing columns: input_per_1k, output_per_1k"]


@pytest.mark.asyncio
async def test_export_round_trips_small_rates_losslessly():
    repo = FakeRateRepo()
    repo._listed = [_row("openai", "gpt-4o-mini", Decimal("0.00015"), Decimal("0.0000001"))]
    service = LlmCostRateService(repo)

    csv_text = await service.export_csv()

    assert csv_text.splitlines()[1] == "openai,gpt-4o-mini,0.00015,0.0000001,,"

    reimport_repo = FakeRateRepo()
    result = await LlmCostRateService(reimport_repo).import_csv(csv_text)
    assert result.inserted == 1
    assert reimport_repo.db.added[0].input_per_1k == Decimal("0.00015")
    assert reimport_repo.db.added[0].output_per_1k == Decimal("0.0000001")
    assert reimport_repo.db.added[0].cache_read_per_1k is None


@pytest.mark.asyncio
async def test_legacy_four_column_file_still_imports_without_cache_rates():
    repo = FakeRateRepo()
    service = LlmCostRateService(repo)

    result = await service.import_csv(HEADER + "anthropic,claude-3-5-sonnet,0.003,0.015\n")

    assert (result.inserted, result.errors) == (1, [])
    added = repo.db.added[0]
    assert added.cache_read_per_1k is None and added.cache_creation_per_1k is None


@pytest.mark.asyncio
async def test_legacy_four_column_file_leaves_configured_cache_rates_alone():
    existing = _row("bedrock", "nova", Decimal("0.0001"), Decimal("0.0004"), Decimal("0.000025"), Decimal("0"))
    service = LlmCostRateService(FakeRateRepo(existing={("bedrock", "nova"): existing}))

    result = await service.import_csv(HEADER + "bedrock,nova,0.0002,0.0008\n")

    assert (result.inserted, result.updated, result.errors) == (0, 1, [])
    assert existing.input_per_1k == Decimal("0.0002")
    assert existing.cache_read_per_1k == Decimal("0.000025")
    assert existing.cache_creation_per_1k == Decimal("0"), "a file without the column cannot clear a rate"


@pytest.mark.asyncio
async def test_import_reads_cache_rates_and_keeps_zero_distinct_from_blank():
    repo = FakeRateRepo()
    service = LlmCostRateService(repo)

    result = await service.import_csv(
        CACHE_HEADER
        + "bedrock,eu.amazon.nova-2-lite-v1:0,0.0001,0.0004,0.000025,0\n"
        + "bedrock,eu.anthropic.claude-3-5-sonnet-20241022-v2:0,0.003,0.015,,\n"
    )

    assert (result.inserted, result.errors) == (2, [])
    nova, claude = repo.db.added
    assert nova.cache_read_per_1k == Decimal("0.000025")
    assert nova.cache_creation_per_1k == Decimal("0"), "free writes are configured, not unset"
    assert claude.cache_read_per_1k is None and claude.cache_creation_per_1k is None


@pytest.mark.asyncio
async def test_import_clears_cache_rates_a_row_no_longer_lists():
    existing = _row("bedrock", "nova", Decimal("0.0001"), Decimal("0.0004"), Decimal("0.000025"), Decimal("0"))
    service = LlmCostRateService(FakeRateRepo(existing={("bedrock", "nova"): existing}))

    result = await service.import_csv(CACHE_HEADER + "bedrock,nova,0.0001,0.0004,,\n")

    assert (result.inserted, result.updated) == (0, 1)
    assert existing.cache_read_per_1k is None and existing.cache_creation_per_1k is None


@pytest.mark.asyncio
async def test_import_rejects_a_negative_cache_rate_row():
    repo = FakeRateRepo()
    service = LlmCostRateService(repo)

    result = await service.import_csv(CACHE_HEADER + "openai,gpt-4o,0.0025,0.01,-0.001,0.001\n")

    assert result.inserted == 0
    assert result.errors == ["Row 2: invalid provider, model or rate value"]


@pytest.mark.asyncio
async def test_export_round_trips_cache_rates():
    repo = FakeRateRepo()
    repo._listed = [
        _row("bedrock", "nova", Decimal("0.0001"), Decimal("0.0004"), Decimal("0.000025"), Decimal("0")),
    ]

    csv_text = await LlmCostRateService(repo).export_csv()

    assert csv_text.splitlines()[0] == (
        "provider,model,input_per_1k,output_per_1k,cache_read_per_1k,cache_creation_per_1k"
    )
    assert csv_text.splitlines()[1] == "bedrock,nova,0.0001,0.0004,0.000025,0"

    reimport_repo = FakeRateRepo()
    await LlmCostRateService(reimport_repo).import_csv(csv_text)
    assert reimport_repo.db.added[0].cache_read_per_1k == Decimal("0.000025")
    assert reimport_repo.db.added[0].cache_creation_per_1k == Decimal("0")
