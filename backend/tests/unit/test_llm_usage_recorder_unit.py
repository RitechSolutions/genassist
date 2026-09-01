"""Unit tests for the LLM usage recorder's pure helpers"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Insert

import app.core.config.llm_pricing as llm_pricing
import app.services.llm_usage_recorder as recorder_module
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.services.llm_usage_recorder import (
    LlmUsageRecorder,
    _clamp,
    _clamp_run_status,
    _normalize,
    _resolve_cost,
    _token_columns,
    _total_tokens,
)


@pytest.fixture(autouse=True)
def _no_db_rates(monkeypatch):
    monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})


class FakeRateRepo:
    def __init__(self, rows):
        self._rows = rows

    async def list_active(self):
        return self._rows


class FakeSession:
    def __init__(self):
        self.rolled_back = False

    async def rollback(self):
        self.rolled_back = True


class CapturingSession(FakeSession):
    def __init__(self, returned_ids=()):
        super().__init__()
        self.statements = []
        self._returned = list(returned_ids)

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(all=lambda: [(i,) for i in self._returned])


class TestNormalize:
    def test_lowercases_trims(self):
        assert _normalize("  OpenAI ", 64) == "openai"

    def test_empty_is_none(self):
        assert _normalize("", 64) is None
        assert _normalize(None, 64) is None

    def test_truncates_to_limit(self):
        assert _normalize("x" * 100, 10) == "x" * 10


class TestClamp:
    def test_preserves_case_unlike_normalize(self):
        assert _clamp("Smart_Route", 64) == "Smart_Route"

    def test_truncates_instead_of_failing_the_insert(self):
        assert _clamp("n" * 300, 128) == "n" * 128

    def test_empty_is_none(self):
        assert _clamp("", 64) is None
        assert _clamp(None, 64) is None


class TestClampRunStatus:
    @pytest.mark.parametrize("status", ["completed", "failed", "paused", "idle", "running"])
    def test_known_statuses_pass_through(self, status):
        assert _clamp_run_status(status) == status

    def test_case_is_normalized(self):
        assert _clamp_run_status(" Paused ") == "paused"

    def test_unknown_status_falls_back_to_completed(self):
        assert _clamp_run_status("exploded") == "completed"
        assert _clamp_run_status(None) == "completed"
        assert _clamp_run_status(42) == "completed"


class TestTotalTokens:
    def test_provider_total_above_parts_wins(self):
        assert _total_tokens({"total_tokens": 500}, 100, 50) == 500

    def test_parts_win_when_total_is_missing_or_low(self):
        assert _total_tokens({}, 100, 50) == 150
        assert _total_tokens({"total_tokens": 1}, 100, 50) == 150

    def test_junk_total_is_ignored(self):
        assert _total_tokens({"total_tokens": "many"}, 3, 4) == 7
        assert _total_tokens({"total_tokens": True}, 3, 4) == 7


class TestResolveCost:
    def test_priced_returns_decimal_cost(self):
        out = _resolve_cost("openai", "gpt-4o", 1000, 500)
        assert out["pricing_status"] == "fallback"
        assert out["input_per_1k"] == Decimal("0.0025")
        assert out["cost_usd"] == Decimal("0.0075")

    def test_longest_prefix_variant(self):
        out = _resolve_cost("openai", "gpt-4o-mini-2024-07-18", 1000, 1000)
        assert out["cost_usd"] == Decimal("0.00075")

    def test_unpriced_keeps_cost_null(self):
        out = _resolve_cost("openai", "totally-unknown-model", 1000, 1000)
        assert out["pricing_status"] == "unpriced"
        assert out["cost_usd"] is None
        assert out["input_per_1k"] is None
        assert out["output_per_1k"] is None

    def test_zero_tokens_priced_is_zero_not_null(self):
        out = _resolve_cost("openai", "gpt-4o", 0, 0)
        assert out["cost_usd"] == Decimal("0")
        assert out["pricing_status"] == "fallback"

    def test_configured_rates_win_and_are_snapshotted(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": Decimal("0.01"), "output_per_1k": Decimal("0.02")}}}
        out = _resolve_cost("openai", "gpt-4o", 1000, 1000, configured)
        assert out["pricing_status"] == "configured"
        assert out["input_per_1k"] == Decimal("0.01")
        assert out["output_per_1k"] == Decimal("0.02")
        assert out["cost_usd"] == Decimal("0.03")

    def test_tiny_configured_rate_costs_exactly(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": Decimal("0.00015"), "output_per_1k": Decimal("0")}}}
        out = _resolve_cost("openai", "gpt-4o", 1_000_000, 500, configured)
        assert out["cost_usd"] == Decimal("0.150")

    def test_bundled_default_provider_stays_unpriced(self):
        out = _resolve_cost("openrouter", "some/model", 10, 10, {})
        assert out["pricing_status"] == "unpriced"
        assert out["cost_usd"] is None


class TestResolveCostCacheBuckets:
    def test_zero_cache_is_identical_to_omitting_the_arguments(self):
        omitted = _resolve_cost("openai", "gpt-4o", 1000, 500)
        explicit = _resolve_cost("openai", "gpt-4o", 1000, 500, cache_read_tokens=0, cache_creation_tokens=0)
        assert omitted == explicit
        assert omitted["cost_usd"] == Decimal("0.0075")

    def test_zero_cache_leaves_rate_snapshots_null(self):
        out = _resolve_cost("openai", "gpt-4o", 1000, 500)
        assert out["cache_read_per_1k"] is None
        assert out["cache_creation_per_1k"] is None

    def test_negative_counts_clamp_and_take_the_zero_cache_path(self):
        out = _resolve_cost("openai", "gpt-4o", 1000, 500, cache_read_tokens=-5, cache_creation_tokens=-1)
        assert out == _resolve_cost("openai", "gpt-4o", 1000, 500)

    def test_anthropic_defaults_to_the_published_multipliers(self):
        out = _resolve_cost(
            "anthropic", "claude-3-5-sonnet", 1000, 200, cache_read_tokens=500, cache_creation_tokens=100
        )
        assert out["cache_read_per_1k"] == Decimal("0.0003")
        assert out["cache_creation_per_1k"] == Decimal("0.00375")
        assert out["cost_usd"] == Decimal("0.004725")

    def test_inclusive_provider_clamps_when_buckets_exceed_input(self):
        out = _resolve_cost("anthropic", "claude-3-5-sonnet", 100, 0, cache_read_tokens=500)
        assert out["cost_usd"] == Decimal("0.00015")

    def test_bedrock_buckets_are_additive_to_the_reported_input(self):
        configured = {
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {
                    "input_per_1k": "0.0001",
                    "output_per_1k": "0.0004",
                    "cache_read_per_1k": "0.0001",
                    "cache_creation_per_1k": "0.0001",
                }
            }
        }
        out = _resolve_cost("bedrock", "us.amazon.nova-2-lite-v1:0", 7, 20, configured, cache_read_tokens=3697)
        assert out["cache_read_per_1k"] == Decimal("0.0001")
        assert out["cache_creation_per_1k"] == Decimal("0.0001")
        assert out["cost_usd"] == Decimal("0.0003784")

    def test_bedrock_without_a_resolved_cache_rate_refuses_a_total(self):
        configured = {"bedrock": {"m": {"input_per_1k": "0.00033", "output_per_1k": "0.00275"}}}
        out = _resolve_cost("bedrock", "m", 7, 20, configured, cache_read_tokens=3697)
        assert out["pricing_status"] == "unpriced"
        assert out["cost_usd"] is None

    def test_the_partial_snapshot_keeps_every_rate_that_was_known(self):
        configured = {"bedrock": {"m": {"input_per_1k": "0.00033", "output_per_1k": "0.00275"}}}
        out = _resolve_cost("bedrock", "m", 7, 20, configured, cache_read_tokens=3697)
        assert out["input_per_1k"] == Decimal("0.00033"), "the base rates were resolved and stay on the row"
        assert out["output_per_1k"] == Decimal("0.00275")
        assert out["cache_read_per_1k"] is None, "only the bucket nobody could price is nulled"
        assert out["cache_creation_per_1k"] is None

    def test_a_bundled_profile_prices_a_cached_call_from_derived_rates(self):
        out = _resolve_cost("bedrock", "eu.amazon.nova-2-lite-v1:0", 7, 20, cache_read_tokens=3697)
        assert out["pricing_status"] == "fallback"
        assert out["input_per_1k"] == Decimal("0.0001"), "base rates come from the bundled EU profile"
        assert out["output_per_1k"] == Decimal("0.0004")
        assert out["cache_read_per_1k"] == Decimal("0.00001")
        assert out["cost_usd"] == Decimal("0.00004567")

    def test_a_totally_unknown_model_still_snapshots_nothing(self):
        out = _resolve_cost("bedrock", "amazon.titan-text-v1", 7, 20, cache_read_tokens=3697)
        assert out["pricing_status"] == "unpriced"
        assert all(out[key] is None for key in ("input_per_1k", "output_per_1k", "cost_usd"))

    def test_configured_cache_rates_are_used_and_snapshotted(self):
        configured = {
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {
                    "input_per_1k": "0.0001",
                    "output_per_1k": "0.0004",
                    "cache_read_per_1k": "0.000025",
                    "cache_creation_per_1k": "0",
                }
            }
        }
        out = _resolve_cost(
            "bedrock",
            "us.amazon.nova-2-lite-v1:0",
            100,
            10,
            configured,
            cache_read_tokens=1000,
            cache_creation_tokens=2000,
        )
        assert out["pricing_status"] == "configured"
        assert out["cache_read_per_1k"] == Decimal("0.000025")
        assert out["cache_creation_per_1k"] == Decimal("0")
        assert out["cost_usd"] == Decimal("0.000039")

    def test_configured_cache_rates_override_the_anthropic_multipliers(self):
        configured = {
            "anthropic": {
                "claude-3-5-sonnet": {
                    "input_per_1k": "0.003",
                    "output_per_1k": "0.015",
                    "cache_read_per_1k": "0.001",
                    "cache_creation_per_1k": "0.002",
                }
            }
        }
        out = _resolve_cost("anthropic", "claude-3-5-sonnet", 1000, 0, configured, cache_read_tokens=500)
        assert out["cache_read_per_1k"] == Decimal("0.001")
        assert out["cache_creation_per_1k"] == Decimal("0.002")

    def test_unpriced_shape_carries_the_snapshot_keys(self):
        out = _resolve_cost("openai", "totally-unknown-model", 1000, 1000, cache_read_tokens=500)
        assert out["pricing_status"] == "unpriced"
        assert out["cache_read_per_1k"] is None
        assert out["cache_creation_per_1k"] is None
        assert out["cost_usd"] is None

    def test_usage_missing_wins_over_cache_counts(self):
        out = _resolve_cost("anthropic", "claude-3-5-sonnet", 1000, 10, usage_missing=True, cache_read_tokens=500)
        assert out["pricing_status"] == "unpriced"
        assert out["cost_usd"] is None

    def test_missing_usage_stays_unpriced_even_with_a_configured_rate(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": Decimal("0.01"), "output_per_1k": Decimal("0.02")}}}
        out = _resolve_cost("openai", "gpt-4o", 0, 0, configured, usage_missing=True)
        assert out["pricing_status"] == "unpriced"
        assert out["cost_usd"] is None
        assert out["input_per_1k"] is None and out["output_per_1k"] is None

    def test_configured_zero_token_call_is_priced_zero_not_unpriced(self):
        configured = {"openai": {"gpt-4o": {"input_per_1k": Decimal("0.01"), "output_per_1k": Decimal("0.02")}}}
        out = _resolve_cost("openai", "gpt-4o", 0, 0, configured)
        assert out["pricing_status"] == "configured"
        assert out["cost_usd"] == Decimal("0")

    def test_blank_provider_and_model_is_unpriced(self):
        out = _resolve_cost("", "", 100, 100, {})
        assert out["pricing_status"] == "unpriced"
        assert out["cost_usd"] is None


class TestConfiguredRatesLoad:
    @staticmethod
    def _rate(provider, model, inp, outp, **cache):
        return SimpleNamespace(provider_key=provider, model_key=model, input_per_1k=inp, output_per_1k=outp, **cache)

    @pytest.mark.asyncio
    async def test_builds_nested_map_and_normalizes_keys(self, monkeypatch):
        rows = [
            self._rate("  OpenAI ", " GPT-4o ", Decimal("0.01"), Decimal("0.02")),
            self._rate("bedrock", "us.amazon.nova-2-lite-v1:0", Decimal("0.1"), Decimal("0.2")),
            self._rate("", "gpt-4o", Decimal("1"), Decimal("1")),
            self._rate("openai", "", Decimal("1"), Decimal("1")),
        ]
        monkeypatch.setattr(recorder_module.injector, "get", lambda _cls: FakeRateRepo(rows))
        session = FakeSession()

        loaded = await LlmUsageRecorder()._configured_rates(session)

        assert loaded == {
            "openai": {
                "gpt-4o": {
                    "input_per_1k": Decimal("0.01"),
                    "output_per_1k": Decimal("0.02"),
                    "cache_read_per_1k": None,
                    "cache_creation_per_1k": None,
                }
            },
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {
                    "input_per_1k": Decimal("0.1"),
                    "output_per_1k": Decimal("0.2"),
                    "cache_read_per_1k": None,
                    "cache_creation_per_1k": None,
                }
            },
        }
        assert session.rolled_back is False

    @pytest.mark.asyncio
    async def test_configured_cache_rates_reach_the_pricing_table(self, monkeypatch):
        rows = [
            self._rate(
                "bedrock",
                "amazon.nova-2-lite-v1:0",
                Decimal("0.0001"),
                Decimal("0.0004"),
                cache_read_per_1k=Decimal("0.000025"),
                cache_creation_per_1k=Decimal("0"),
            )
        ]
        monkeypatch.setattr(recorder_module.injector, "get", lambda _cls: FakeRateRepo(rows))

        loaded = await LlmUsageRecorder()._configured_rates(FakeSession())

        assert loaded["bedrock"]["amazon.nova-2-lite-v1:0"]["cache_read_per_1k"] == Decimal("0.000025")
        assert loaded["bedrock"]["amazon.nova-2-lite-v1:0"]["cache_creation_per_1k"] == Decimal("0")
        priced = _resolve_cost("bedrock", "eu.amazon.nova-2-lite-v1:0", 100, 0, loaded, cache_read_tokens=1000)
        assert priced["pricing_status"] == "configured"
        assert priced["cost_usd"] == Decimal("0.000035"), "1000 cache reads at the configured rate plus 100 input"

    @pytest.mark.asyncio
    async def test_load_failure_degrades_to_bundled_and_rolls_back(self, monkeypatch):
        def boom(_cls):
            raise RuntimeError("rates table unavailable")

        monkeypatch.setattr(recorder_module.injector, "get", boom)
        session = FakeSession()

        loaded = await LlmUsageRecorder()._configured_rates(session)

        assert loaded == {}
        assert session.rolled_back is True
        assert _resolve_cost("openai", "gpt-4o", 1000, 0, loaded)["pricing_status"] == "fallback"


class TestExistingIds:
    @pytest.mark.asyncio
    async def test_bypasses_group_scope_so_attribution_survives(self):
        agent_id = uuid4()
        session = CapturingSession([agent_id])

        found = await LlmUsageRecorder()._existing_ids(session, AgentModel, {agent_id})

        assert found == {agent_id}
        assert session.statements[0].get_execution_options().get(GROUP_SCOPE_BYPASS_FLAG) is True

    @pytest.mark.asyncio
    async def test_absent_ids_are_still_dropped(self):
        present, absent = uuid4(), uuid4()
        session = CapturingSession([present])

        found = await LlmUsageRecorder()._existing_ids(session, AgentModel, {present, absent})

        assert found == {present}

    @pytest.mark.asyncio
    async def test_no_query_when_every_id_is_none(self):
        session = CapturingSession()

        assert await LlmUsageRecorder()._existing_ids(session, AgentModel, {None}) == set()
        assert session.statements == []


class TestAgentForWorkflow:
    @pytest.mark.asyncio
    async def test_single_owner_is_derived(self):
        agent_id = uuid4()
        session = CapturingSession([agent_id])

        assert await LlmUsageRecorder()._agent_for_workflow(session, uuid4()) == agent_id

    @pytest.mark.asyncio
    async def test_unowned_workflow_stays_unattributed(self):
        session = CapturingSession()

        assert await LlmUsageRecorder()._agent_for_workflow(session, uuid4()) is None

    @pytest.mark.asyncio
    async def test_shared_workflow_is_too_ambiguous_to_attribute(self):
        session = CapturingSession([uuid4(), uuid4()])

        assert await LlmUsageRecorder()._agent_for_workflow(session, uuid4()) is None

    @pytest.mark.asyncio
    async def test_no_query_without_a_workflow(self):
        session = CapturingSession([uuid4()])

        assert await LlmUsageRecorder()._agent_for_workflow(session, None) is None
        assert session.statements == []

    @pytest.mark.asyncio
    async def test_lookup_bypasses_group_scope_and_skips_deleted_owners(self):
        workflow_id = uuid4()
        session = CapturingSession([uuid4()])

        await LlmUsageRecorder()._agent_for_workflow(session, workflow_id)

        stmt = session.statements[0]
        assert stmt.get_execution_options().get(GROUP_SCOPE_BYPASS_FLAG) is True
        sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        assert f"agents.workflow_id = '{workflow_id}'" in sql
        assert "agents.is_deleted = 0" in sql


class RecordingSession(FakeSession):
    def __init__(self):
        super().__init__()
        self.statements = []
        self.committed = False

    async def execute(self, stmt):
        self.statements.append(stmt)
        return SimpleNamespace(all=lambda: [], scalar=lambda: 0, scalar_one_or_none=lambda: True)

    async def scalar(self, stmt):
        return True

    async def commit(self):
        self.committed = True

    async def close(self):
        pass


@pytest.fixture
def record_scope(monkeypatch):
    @asynccontextmanager
    async def _scope():
        yield

    session = RecordingSession()
    monkeypatch.setattr(recorder_module, "create_tenant_request_scope", _scope)
    monkeypatch.setattr(
        recorder_module.injector, "get", lambda cls: session if cls is AsyncSession else FakeRateRepo([])
    )
    recorder_module._capture_slots.clear()
    yield session
    recorder_module._capture_slots.clear()


def _bound_values(statements):
    return {
        value
        for stmt in statements
        if isinstance(stmt, Insert)
        for value in stmt.compile(dialect=postgresql.dialect()).params.values()
    }


def _state(**kwargs):
    return SimpleNamespace(
        execution_id=str(uuid4()),
        llm_usage=[{"provider": "openai", "model": "gpt-4o", "input_tokens": 10, "output_tokens": 5}],
        thread_id=None,
        status="completed",
        **kwargs,
    )


class TestOccurredAt:
    @pytest.mark.asyncio
    async def test_passed_stamp_wins_over_the_recording_clock(self, record_scope, monkeypatch):
        scheduled = datetime(2026, 7, 20, 23, 59, 30, tzinfo=timezone.utc)
        recorded = datetime(2026, 7, 21, 0, 0, 15, tzinfo=timezone.utc)
        monkeypatch.setattr(recorder_module, "utc_now", lambda: recorded)

        await LlmUsageRecorder().record_workflow_state(
            _state(), WorkflowUsageContext(source="chat"), "returned", occurred_at=scheduled
        )

        values = _bound_values(record_scope.statements)
        assert record_scope.committed
        assert scheduled in values
        assert recorded not in values

    @pytest.mark.asyncio
    async def test_omitting_it_falls_back_to_the_recording_clock(self, record_scope, monkeypatch):
        recorded = datetime(2026, 7, 21, 0, 0, 15, tzinfo=timezone.utc)
        monkeypatch.setattr(recorder_module, "utc_now", lambda: recorded)

        await LlmUsageRecorder().record_workflow_state(_state(), WorkflowUsageContext(source="schedule"), "returned")

        assert recorded in _bound_values(record_scope.statements)


class TestCaptureBound:
    @pytest.mark.asyncio
    async def test_concurrent_captures_are_capped_per_loop(self, record_scope, monkeypatch):
        monkeypatch.setattr(recorder_module, "_CAPTURE_CONCURRENCY", 1)
        active, peak = 0, 0

        async def _slow_gate(_self, _session):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return False

        monkeypatch.setattr(LlmUsageRecorder, "_capture_enabled", _slow_gate)
        recorder = LlmUsageRecorder()
        ctx = WorkflowUsageContext(source="chat")

        await asyncio.gather(
            recorder.record_workflow_state(_state(), ctx, "returned"),
            recorder.record_workflow_state(_state(), ctx, "returned"),
        )

        assert peak == 1

    def test_slot_is_rebuilt_for_a_fresh_loop(self):
        recorder_module._capture_slots.clear()

        async def hold(slot):
            async with slot:
                await asyncio.sleep(0)

        async def contend():
            slot = recorder_module._capture_slot()
            await asyncio.gather(*(hold(slot) for _ in range(recorder_module._CAPTURE_CONCURRENCY + 2)))

        asyncio.run(contend())
        asyncio.run(contend())

        recorder_module._capture_slots.clear()


class EvaluationSession(FakeSession):
    def __init__(
        self, *, workflows=(), providers=(), agents=(), workflow_agents=None, persisted=0, capture_enabled=True
    ):
        super().__init__()
        self.statements = []
        self.committed = False
        self.closed = False
        self._by_table = {"workflows": list(workflows), "llm_providers": list(providers), "agents": list(agents)}
        self._workflow_agents = workflow_agents
        self._persisted = persisted
        self._capture_enabled = capture_enabled

    def _ids_for(self, stmt):
        sql = str(stmt)
        if "agents.workflow_id" in sql and self._workflow_agents is not None:
            return self._workflow_agents
        for table, ids in self._by_table.items():
            if f"FROM {table}" in sql:
                return ids
        return []

    async def execute(self, stmt):
        self.statements.append(stmt)
        ids = self._ids_for(stmt)
        return SimpleNamespace(
            all=lambda: [(i,) for i in ids],
            scalar=lambda: self._persisted,
            scalar_one_or_none=lambda: self._capture_enabled,
        )

    async def commit(self):
        self.committed = True

    async def close(self):
        self.closed = True


@pytest.fixture
def evaluation_scope(monkeypatch):
    @asynccontextmanager
    async def _scope():
        yield

    sessions = []

    def _install(session):
        sessions.append(session)
        monkeypatch.setattr(recorder_module, "create_tenant_request_scope", _scope)
        monkeypatch.setattr(
            recorder_module.injector, "get", lambda cls: session if cls is AsyncSession else FakeRateRepo([])
        )
        recorder_module._capture_slots.clear()
        return session

    yield _install
    recorder_module._capture_slots.clear()


def _insert_for(statements, table: str):
    return next(s for s in statements if isinstance(s, Insert) and s.table.name == table)


def _rows_of(stmt) -> list[dict]:
    params = stmt.compile(dialect=postgresql.dialect()).params
    rows: dict[int, dict] = {}
    for key, value in params.items():
        name, _, index = key.rpartition("_m")
        if index.isdigit():
            rows.setdefault(int(index), {})[name] = value
    return [rows[i] for i in sorted(rows)] if rows else [params]


_JUDGE_USAGE = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}


def _entry(call_index=0, purpose="llm_judge", provider="openai", model="gpt-4o", usage=_JUDGE_USAGE, provider_id=None):
    return {
        "call_index": call_index,
        "purpose": purpose,
        "provider": provider,
        "model": model,
        "usage": usage,
        "llm_provider_id": provider_id,
    }


class TestRecordEvaluationCalls:
    @pytest.mark.asyncio
    async def test_empty_entries_never_touch_the_database(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [])

        assert session.statements == [] and session.committed is False

    @pytest.mark.asyncio
    async def test_inert_while_capture_is_disabled(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession(capture_enabled=False))

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry()])

        assert not [s for s in session.statements if isinstance(s, Insert)]
        assert session.committed is False

    @pytest.mark.asyncio
    async def test_events_and_receipt_are_written_in_one_commit(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession(persisted=2))

        await LlmUsageRecorder().record_evaluation_calls(
            "eval:abc", [_entry(0, "llm_judge"), _entry(1, "provenance_judge")]
        )

        inserts = [s for s in session.statements if isinstance(s, Insert)]
        assert len(inserts) == 2, "one batched events insert plus one receipt"
        assert session.committed is True and session.closed is True

    @pytest.mark.asyncio
    async def test_every_event_carries_the_evaluation_source_type_and_its_purpose(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        await LlmUsageRecorder().record_evaluation_calls(
            "eval:abc", [_entry(0, "llm_judge"), _entry(3, "provenance_judge")]
        )

        rows = _rows_of(_insert_for(session.statements, "llm_usage_events"))
        assert [r["source_type"] for r in rows] == ["evaluation", "evaluation"]
        assert [r["source"] for r in rows] == ["test_suite", "test_suite"]
        assert [r["purpose"] for r in rows] == ["llm_judge", "provenance_judge"]
        assert [r["call_index"] for r in rows] == [0, 3], "gaps in technique positions are kept as-is"

    @pytest.mark.asyncio
    async def test_one_receipt_reports_expected_and_persisted_counts(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession(persisted=2))

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry(0), _entry(1)])

        receipt = _rows_of(_insert_for(session.statements, "llm_usage_capture_runs"))[0]
        assert receipt["execution_id"] == "eval:abc"
        assert receipt["source_type"] == "evaluation"
        assert (receipt["expected_entries"], receipt["persisted_events"]) == (2, 2)
        assert (receipt["execution_outcome"], receipt["run_status"]) == ("returned", "completed")

    @pytest.mark.asyncio
    async def test_events_are_priced_from_their_own_usage(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry()])

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        assert (row["input_tokens"], row["output_tokens"], row["total_tokens"]) == (100, 50, 150)
        assert row["pricing_status"] == "fallback" and row["cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_missing_usage_still_counts_the_call_but_stays_unpriced(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry(usage=None)])

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        assert row["total_tokens"] == 0
        assert row["pricing_status"] == "unpriced" and row["cost_usd"] is None

    @pytest.mark.asyncio
    async def test_agent_is_derived_from_the_validated_workflow(self, evaluation_scope):
        workflow_id, agent_id = uuid4(), uuid4()
        session = evaluation_scope(EvaluationSession(workflows=[workflow_id], agents=[agent_id]))

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry()], workflow_id=workflow_id)

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        receipt = _rows_of(_insert_for(session.statements, "llm_usage_capture_runs"))[0]
        assert row["workflow_id"] == workflow_id and row["agent_id"] == agent_id
        assert receipt["workflow_id"] == workflow_id and receipt["agent_id"] == agent_id

    @pytest.mark.asyncio
    async def test_an_explicit_owner_outranks_the_workflows_active_agent(self, evaluation_scope):
        workflow_id, historical_owner, active_agent = uuid4(), uuid4(), uuid4()
        session = evaluation_scope(
            EvaluationSession(workflows=[workflow_id], agents=[historical_owner], workflow_agents=[active_agent])
        )

        await LlmUsageRecorder().record_evaluation_calls(
            "eval:abc", [_entry()], workflow_id=workflow_id, agent_id=historical_owner
        )

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        receipt = _rows_of(_insert_for(session.statements, "llm_usage_capture_runs"))[0]
        assert row["agent_id"] == historical_owner, "the evaluated version's owner, not whoever runs it now"
        assert receipt["agent_id"] == historical_owner

    @pytest.mark.asyncio
    async def test_an_unknown_owner_falls_back_to_the_workflows_active_agent(self, evaluation_scope):
        workflow_id, active_agent = uuid4(), uuid4()
        session = evaluation_scope(
            EvaluationSession(workflows=[workflow_id], agents=[], workflow_agents=[active_agent])
        )

        await LlmUsageRecorder().record_evaluation_calls(
            "eval:abc", [_entry()], workflow_id=workflow_id, agent_id=uuid4()
        )

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        assert row["agent_id"] == active_agent

    @pytest.mark.asyncio
    async def test_an_absent_owner_keeps_deriving_the_agent_from_the_workflow(self, evaluation_scope):
        workflow_id, active_agent = uuid4(), uuid4()
        session = evaluation_scope(
            EvaluationSession(workflows=[workflow_id], agents=[], workflow_agents=[active_agent])
        )

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry()], workflow_id=workflow_id)

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        assert row["agent_id"] == active_agent

    @pytest.mark.asyncio
    async def test_unknown_workflow_and_provider_are_nulled_not_rejected(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry(provider_id=uuid4())], workflow_id=uuid4())

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        assert row["workflow_id"] is None and row["llm_provider_id"] is None and row["agent_id"] is None

    @pytest.mark.asyncio
    async def test_events_insert_is_idempotent_on_execution_and_call_index(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry()])

        events = _insert_for(session.statements, "llm_usage_events")
        receipt = _insert_for(session.statements, "llm_usage_capture_runs")
        assert events._post_values_clause is not None, "events must be ON CONFLICT DO NOTHING"
        assert receipt._post_values_clause is not None, "the receipt must be ON CONFLICT DO NOTHING"

    @pytest.mark.asyncio
    async def test_a_write_failure_rolls_back_and_never_raises(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        async def boom(_stmt):
            raise RuntimeError("ledger unavailable")

        session.execute = boom

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry()])

        assert session.rolled_back is True and session.committed is False


class TestWorkflowUsageContext:
    def test_defaults(self):
        ctx = WorkflowUsageContext(source="chat")
        assert ctx.source == "chat"
        assert ctx.source_type == "workflow"
        assert ctx.agent_id is None and ctx.workflow_id is None and ctx.conversation_id is None
        assert ctx.defer_capture is False

    def test_fields(self):
        aid = uuid4()
        ctx = WorkflowUsageContext(source="schedule", agent_id=aid)
        assert isinstance(ctx.agent_id, UUID)
        assert ctx.agent_id == aid


class TestTokenColumns:
    def test_cache_counts_are_read_from_the_token_details(self):
        details = {"input_token_details": {"cache_read": 3697, "cache_creation": 60}}

        assert _token_columns("bedrock", {"total_tokens": 3724}, 7, 20, details) == {
            "input_tokens": 7,
            "output_tokens": 20,
            "total_tokens": 3724,
            "token_details": details,
            "cache_read_tokens": 3697,
            "cache_creation_tokens": 60,
            "prompt_tokens": 3764,
        }

    def test_stored_counts_stay_provider_raw(self):
        columns = _token_columns("bedrock", {}, 7, 20, {"input_token_details": {"cache_read": 3697}})

        assert columns["input_tokens"] == 7
        assert columns["total_tokens"] == 27, "unchanged max(reported, in+out)"

    def test_prompt_tokens_add_the_cache_buckets_only_for_exclusive_providers(self):
        details = {"input_token_details": {"cache_read": 3697, "cache_creation": 60}}

        assert _token_columns("bedrock", {}, 7, 20, details)["prompt_tokens"] == 3764
        assert _token_columns("anthropic", {}, 3764, 20, details)["prompt_tokens"] == 3764

    def test_prompt_tokens_are_normalized_before_the_provider_lookup(self):
        details = {"input_token_details": {"cache_read": 100}}

        assert _token_columns("  Bedrock ", {}, 7, 20, details)["prompt_tokens"] == 107

    @pytest.mark.parametrize("details", [None, {}, "junk", {"usage_metadata_missing": True}])
    def test_entries_without_cache_details_count_zero(self, details):
        columns = _token_columns("bedrock", {}, 10, 5, details)

        assert (columns["cache_read_tokens"], columns["cache_creation_tokens"]) == (0, 0)
        assert columns["prompt_tokens"] == 10, "an uncached call keeps the reported input count"


_CACHED_DETAILS = {"input_token_details": {"cache_read": 500, "cache_creation": 60}}


class TestCacheColumnWiring:

    @pytest.mark.asyncio
    async def test_workflow_rows_carry_counts_and_snapshots(self, record_scope):
        state = SimpleNamespace(
            execution_id=str(uuid4()),
            llm_usage=[
                {
                    "provider": "bedrock",
                    "model": "eu.amazon.nova-2-lite-v1:0",
                    "input_tokens": 7,
                    "output_tokens": 20,
                    "total_tokens": 3724,
                    "token_details": {"input_token_details": {"cache_read": 3697, "cache_creation": 0}},
                }
            ],
            thread_id=None,
            status="completed",
        )

        await LlmUsageRecorder().record_workflow_state(state, WorkflowUsageContext(source="chat"), "returned")

        row = _rows_of(_insert_for(record_scope.statements, "llm_usage_events"))[0]
        assert (row["cache_read_tokens"], row["cache_creation_tokens"]) == (3697, 0)
        assert row["input_tokens"] == 7, "provider-raw, not inflated by the cached prefix"
        assert row["cost_usd"] == Decimal("0.00004567") and row["pricing_status"] == "fallback"
        assert row["input_per_1k"] == Decimal("0.0001")
        assert (row["cache_read_per_1k"], row["cache_creation_per_1k"]) == (Decimal("0.00001"), Decimal("0.000125"))
        assert row["prompt_tokens"] == 3704, "bedrock reports input without the cache buckets"

    @pytest.mark.asyncio
    async def test_evaluation_rows_carry_counts_and_snapshots(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())
        usage = {"input_tokens": 660, "output_tokens": 10, "total_tokens": 670, "token_details": _CACHED_DETAILS}

        await LlmUsageRecorder().record_evaluation_calls(
            "eval:abc", [_entry(provider="anthropic", model="claude-3-5-sonnet", usage=usage)]
        )

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        assert (row["cache_read_tokens"], row["cache_creation_tokens"]) == (500, 60)
        assert row["cache_read_per_1k"] == Decimal("0.0003"), "0.1x of the anthropic input rate"
        assert row["prompt_tokens"] == 660, "anthropic already counts the cache buckets in"

    @pytest.mark.asyncio
    async def test_analyst_row_carries_counts_and_snapshots(self, record_scope):
        await LlmUsageRecorder().record_analyst_call(
            "analysis:1",
            0,
            "anthropic",
            "claude-3-5-sonnet",
            usage={"input_tokens": 660, "output_tokens": 10, "total_tokens": 670, "token_details": _CACHED_DETAILS},
        )

        row = _rows_of(_insert_for(record_scope.statements, "llm_usage_events"))[0]
        assert (row["cache_read_tokens"], row["cache_creation_tokens"]) == (500, 60)
        assert row["cache_creation_per_1k"] == Decimal("0.00375"), "1.25x of the anthropic input rate"

    @pytest.mark.asyncio
    async def test_uncached_rows_keep_zero_counts_and_null_snapshots(self, evaluation_scope):
        session = evaluation_scope(EvaluationSession())

        await LlmUsageRecorder().record_evaluation_calls("eval:abc", [_entry()])

        row = _rows_of(_insert_for(session.statements, "llm_usage_events"))[0]
        assert (row["cache_read_tokens"], row["cache_creation_tokens"]) == (0, 0)
        assert (row["cache_read_per_1k"], row["cache_creation_per_1k"]) == (None, None)
        assert row["prompt_tokens"] == row["input_tokens"], "an uncached call needs no adjustment"
