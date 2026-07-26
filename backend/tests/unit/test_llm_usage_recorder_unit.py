"""Unit tests for the LLM usage recorder's pure helpers"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import app.core.config.llm_pricing as llm_pricing
import app.services.llm_usage_recorder as recorder_module
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.services.llm_usage_recorder import (
    LlmUsageRecorder,
    WorkflowUsageContext,
    _clamp,
    _clamp_run_status,
    _coerce_uuid,
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


class TestCoerceUuid:
    def test_passthrough_uuid(self):
        u = uuid4()
        assert _coerce_uuid(u) is u

    def test_string_uuid(self):
        u = uuid4()
        assert _coerce_uuid(str(u)) == u

    def test_none(self):
        assert _coerce_uuid(None) is None

    def test_garbage_returns_none(self):
        assert _coerce_uuid("not-a-uuid") is None
        assert _coerce_uuid("mcp_tool_abc") is None
        assert _coerce_uuid(12345) is None


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


class TestWorkflowUsageContext:
    def test_defaults(self):
        ctx = WorkflowUsageContext(source="chat")
        assert ctx.source == "chat"
        assert ctx.source_type == "workflow"
        assert ctx.agent_id is None and ctx.workflow_id is None and ctx.conversation_id is None

    def test_fields(self):
        aid = uuid4()
        ctx = WorkflowUsageContext(source="schedule", agent_id=aid)
        assert isinstance(ctx.agent_id, UUID)
        assert ctx.agent_id == aid
