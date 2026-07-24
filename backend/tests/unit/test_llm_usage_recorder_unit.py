"""Unit tests for the LLM usage recorder's pure helpers"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest

import app.core.config.llm_pricing as llm_pricing
from app.services.llm_usage_recorder import (
    WorkflowUsageContext,
    _coerce_uuid,
    _normalize,
    _resolve_cost,
)


@pytest.fixture(autouse=True)
def _no_db_rates(monkeypatch):
    monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})


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


class TestWorkflowUsageContext:
    def test_defaults(self):
        ctx = WorkflowUsageContext(source="chat")
        assert ctx.source == "chat"
        assert ctx.source_type == "workflow"
        assert ctx.agent_id is None and ctx.workflow_id is None and ctx.conversation_id is None
        assert ctx.extra == {}

    def test_fields(self):
        aid = uuid4()
        ctx = WorkflowUsageContext(source="schedule", agent_id=aid)
        assert isinstance(ctx.agent_id, UUID)
        assert ctx.agent_id == aid
