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
    def _rate(provider, model, inp, outp):
        return SimpleNamespace(provider_key=provider, model_key=model, input_per_1k=inp, output_per_1k=outp)

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
            "openai": {"gpt-4o": {"input_per_1k": Decimal("0.01"), "output_per_1k": Decimal("0.02")}},
            "bedrock": {
                "us.amazon.nova-2-lite-v1:0": {"input_per_1k": Decimal("0.1"), "output_per_1k": Decimal("0.2")}
            },
        }
        assert session.rolled_back is False

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

        await LlmUsageRecorder().record_workflow_state(
            _state(), WorkflowUsageContext(source="schedule"), "returned"
        )

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
