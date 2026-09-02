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
        self._listed: list = list(self._existing.values())
        self.list_active_calls = 0
        self.lookup_calls = 0

    async def get_active_by_provider_model(self, provider, model):
        self.lookup_calls += 1
        return self._existing.get((provider, model))

    async def list_active(self):
        self.list_active_calls += 1
        return self._listed


@pytest.fixture(autouse=True)
def _configure_mappers(app_def):
    return app_def


@pytest.fixture(autouse=True)
def cache_invalidations(monkeypatch):
    calls: list = []
    monkeypatch.setattr(rate_module, "invalidate_llm_cost_rates_cache", lambda tenant=None: calls.append(tenant))
    monkeypatch.setattr(rate_module, "get_tenant_context", lambda: "tenant-1")
    return calls


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

    csv_text = await service.export_csv(True)

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

    csv_text = await LlmCostRateService(repo).export_csv(True)

    assert csv_text.splitlines()[0] == (
        "provider,model,input_per_1k,output_per_1k,cache_read_per_1k,cache_creation_per_1k"
    )
    assert csv_text.splitlines()[1] == "bedrock,nova,0.0001,0.0004,0.000025,0"

    reimport_repo = FakeRateRepo()
    await LlmCostRateService(reimport_repo).import_csv(csv_text)
    assert reimport_repo.db.added[0].cache_read_per_1k == Decimal("0.000025")
    assert reimport_repo.db.added[0].cache_creation_per_1k == Decimal("0")


@pytest.mark.asyncio
async def test_export_defaults_to_the_four_column_layout():
    repo = FakeRateRepo()
    repo._listed = [_row("bedrock", "nova", Decimal("0.0001"), Decimal("0.0004"), Decimal("0.000025"), Decimal("0"))]

    csv_text = await LlmCostRateService(repo).export_csv(False)

    assert csv_text.splitlines() == [
        "provider,model,input_per_1k,output_per_1k",
        "bedrock,nova,0.0001,0.0004",
    ]


@pytest.mark.asyncio
async def test_four_column_export_re_imports_without_touching_cache_rates():
    configured = _row("bedrock", "nova", Decimal("0.0001"), Decimal("0.0004"), Decimal("0.000025"), Decimal("0"))
    repo = FakeRateRepo(existing={("bedrock", "nova"): configured})

    csv_text = await LlmCostRateService(repo).export_csv(False)
    result = await LlmCostRateService(repo).import_csv(csv_text)

    assert (result.inserted, result.updated, result.errors) == (0, 1, [])
    assert configured.cache_read_per_1k == Decimal("0.000025")
    assert configured.cache_creation_per_1k == Decimal("0")


@pytest.mark.asyncio
async def test_six_column_export_round_trips_an_unset_cache_rate_as_unset():
    unset = _row("openai", "gpt-4o", Decimal("0.0025"), Decimal("0.01"))
    repo = FakeRateRepo(existing={("openai", "gpt-4o"): unset})

    csv_text = await LlmCostRateService(repo).export_csv(True)
    result = await LlmCostRateService(repo).import_csv(csv_text)

    assert (result.inserted, result.updated, result.errors) == (0, 1, [])
    assert unset.cache_read_per_1k is None and unset.cache_creation_per_1k is None


@pytest.mark.asyncio
async def test_import_rejects_a_file_over_the_row_cap_before_staging_anything():
    repo = FakeRateRepo()
    body = "".join(f"openai,model-{i},0.001,0.002\n" for i in range(rate_module.MAX_IMPORT_ROWS + 1))

    result = await LlmCostRateService(repo).import_csv(HEADER + body)

    assert (result.inserted, result.updated) == (0, 0)
    assert result.errors == [f"CSV has more than {rate_module.MAX_IMPORT_ROWS} data rows"]
    assert repo.db.added == [] and repo.db.committed is False
    assert repo.list_active_calls == 0


@pytest.mark.asyncio
async def test_import_accepts_a_file_exactly_at_the_row_cap():
    repo = FakeRateRepo()
    body = "".join(f"openai,model-{i},0.001,0.002\n" for i in range(rate_module.MAX_IMPORT_ROWS))

    result = await LlmCostRateService(repo).import_csv(HEADER + body)

    assert result.inserted == rate_module.MAX_IMPORT_ROWS


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "header,expected",
    [
        ("provider,model,input_per_1k,output_per_1k,provider\n", "provider"),
        ("provider,MODEL,input_per_1k,output_per_1k, model \n", "model"),
    ],
    ids=["identical", "case_and_whitespace_variant"],
)
async def test_import_rejects_duplicate_headers(header, expected):
    repo = FakeRateRepo()

    result = await LlmCostRateService(repo).import_csv(header + "openai,gpt-4o,0.001,0.002\n")

    assert result.errors == [f"Duplicate columns: {expected}"]
    assert repo.db.added == []


@pytest.mark.asyncio
async def test_import_caps_the_error_list_and_reports_the_omitted_count():
    repo = FakeRateRepo()
    body = "".join(f"openai,model-{i},abc,0.002\n" for i in range(rate_module.MAX_IMPORT_ERRORS + 25))

    result = await LlmCostRateService(repo).import_csv(HEADER + body)

    assert len(result.errors) == rate_module.MAX_IMPORT_ERRORS + 1
    assert result.errors[-1] == "… 25 additional errors omitted"
    assert result.errors[0].startswith("Row 2:")


@pytest.mark.asyncio
async def test_import_looks_up_existing_rates_once_for_the_whole_file():
    existing = {
        ("openai", "gpt-4o"): _row("openai", "gpt-4o", Decimal("0.001"), Decimal("0.002")),
        ("openai", "gpt-4o-mini"): _row("openai", "gpt-4o-mini", Decimal("0.0001"), Decimal("0.0002")),
    }
    repo = FakeRateRepo(existing=existing)

    result = await LlmCostRateService(repo).import_csv(
        HEADER
        + "openai,gpt-4o,0.009,0.02\n"
        + "openai,gpt-4o-mini,0.0009,0.002\n"
        + "anthropic,claude-3-opus,0.015,0.075\n"
    )

    assert (result.inserted, result.updated, result.errors) == (1, 2, [])
    assert repo.list_active_calls == 1
    assert repo.lookup_calls == 0, "one prefetch replaces the per-row query"


@pytest.mark.asyncio
async def test_import_that_changes_nothing_leaves_the_pricing_cache_alone(cache_invalidations):
    repo = FakeRateRepo()

    result = await LlmCostRateService(repo).import_csv(HEADER + "openai,gpt-4o,abc,0.002\n")

    assert (result.inserted, result.updated) == (0, 0)
    assert cache_invalidations == []


@pytest.mark.asyncio
async def test_import_that_writes_rows_invalidates_the_pricing_cache(cache_invalidations):
    repo = FakeRateRepo()

    await LlmCostRateService(repo).import_csv(HEADER + "openai,gpt-4o,0.001,0.002\n")

    assert cache_invalidations == ["tenant-1"]


def test_byte_cap_admits_a_file_exactly_at_the_limit():
    assert rate_module.import_exceeds_byte_cap(b"x" * rate_module.MAX_IMPORT_BYTES) is False
    assert rate_module.import_exceeds_byte_cap(b"x" * (rate_module.MAX_IMPORT_BYTES + 1)) is True
@pytest.mark.asyncio
async def test_import_matches_headers_ignoring_case_and_surrounding_space():
    repo = FakeRateRepo()

    result = await LlmCostRateService(repo).import_csv(
        " Provider , MODEL ,Input_Per_1K,output_per_1k\nopenai,gpt-4o,0.001,0.002\n"
    )

    assert (result.inserted, result.errors) == (1, [])
    assert repo.db.added[0].input_per_1k == Decimal("0.001")


@pytest.mark.asyncio
async def test_import_reads_a_short_row_as_blank_cells():
    repo = FakeRateRepo()

    result = await LlmCostRateService(repo).import_csv(CACHE_HEADER + "openai,gpt-4o,0.001,0.002\n")

    assert (result.inserted, result.errors) == (1, [])
    added = repo.db.added[0]
    assert added.cache_read_per_1k is None and added.cache_creation_per_1k is None


@pytest.mark.asyncio
@pytest.mark.parametrize("padding", [",,", ",  ,\t", ", ,"], ids=["empty", "spaces_and_tab", "single_space"])
async def test_padded_header_columns_are_not_read_as_duplicates(padding):
    repo = FakeRateRepo()

    result = await LlmCostRateService(repo).import_csv(
        f"provider,model,input_per_1k,output_per_1k{padding}\nopenai,gpt-4o,0.001,0.002,,\n"
    )

    assert (result.inserted, result.errors) == (1, [])
