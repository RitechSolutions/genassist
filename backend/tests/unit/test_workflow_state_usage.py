"""Unit tests for WorkflowState LLM-usage plumbing (correlation id + sink semantics)"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config.settings import settings
from app.modules.workflow.engine.llm_usage_tracking import merge_llm_usage_from_result
from app.modules.workflow.engine.workflow_state import WorkflowState

WF = {"config": {"id": "wf-1"}, "nodes": [], "edges": []}
THREAD = "11111111-1111-1111-1111-111111111111"


def _state() -> WorkflowState:
    return WorkflowState(workflow=WF, thread_id=THREAD, initial_values={"message": "hi"})


def _caching_provider_injector():
    provider = SimpleNamespace(
        llm_model_provider="Anthropic",
        llm_model="claude-3-opus",
        connection_data={"prompt_caching_enabled": True},
    )
    service = MagicMock(get_by_id=AsyncMock(return_value=provider))
    return patch("app.dependencies.injector.injector", MagicMock(get=MagicMock(return_value=service)))


class TestAddLlmUsage:
    def test_stores_new_fields(self):
        s = _state()
        s.add_llm_usage(
            10, 5, provider="openai", model="gpt-4o", node_id="n1",
            purpose="smart_route", token_details={"cache": 1}, llm_provider_id="pid-1",
        )
        entry = s.llm_usage[0]
        assert entry["purpose"] == "smart_route"
        assert entry["token_details"] == {"cache": 1}
        assert entry["llm_provider_id"] == "pid-1"

    def test_defaults_are_none(self):
        s = _state()
        s.add_llm_usage(1, 1)
        entry = s.llm_usage[0]
        assert entry["purpose"] is None
        assert entry["token_details"] is None
        assert entry["llm_provider_id"] is None
        assert entry["prompt_caching_enabled"] is False


class TestTotalLlmUsageCacheTokens:
    def test_cache_keys_are_omitted_when_caching_is_off(self):
        s = _state()
        s.add_llm_usage(10, 5, provider="anthropic", model="claude-3-5-sonnet")
        usage = s.get_total_llm_usage()
        assert "cache_read_tokens" not in usage
        assert "cache_creation_tokens" not in usage
        assert usage["input_tokens"] == 10 and usage["calls"] == 1

    def test_toggle_on_but_nothing_cached_still_reports_zeros(self):
        s = _state()
        s.add_llm_usage(10, 5, provider="anthropic", model="claude-3-5-sonnet", prompt_caching_enabled=True)
        usage = s.get_total_llm_usage()
        assert usage["cache_read_tokens"] == 0
        assert usage["cache_creation_tokens"] == 0

    def test_reported_cache_activity_surfaces_without_a_toggle(self):
        s = _state()
        details = {"input_token_details": {"cache_read": 1200}}
        s.add_llm_usage(10, 5, provider="openai", model="gpt-4o", token_details=details)
        usage = s.get_total_llm_usage()
        assert usage["cache_read_tokens"] == 1200
        assert usage["cache_creation_tokens"] == 0

    def test_one_caching_provider_surfaces_the_keys_for_the_run(self):
        s = _state()
        s.add_llm_usage(10, 5, provider="openai", model="gpt-4o")
        s.add_llm_usage(10, 5, provider="anthropic", model="claude-3-5-sonnet", prompt_caching_enabled=True)
        assert "cache_read_tokens" in s.get_total_llm_usage()

    def test_toggle_on_with_cache_activity_reports_real_counts(self):
        s = _state()
        details = {"input_token_details": {"cache_read": 300, "cache_creation": 20}}
        s.add_llm_usage(10, 5, provider="anthropic", token_details=details, prompt_caching_enabled=True)
        usage = s.get_total_llm_usage()
        assert (usage["cache_read_tokens"], usage["cache_creation_tokens"]) == (300, 20)

    def test_cache_counts_are_summed_across_entries(self):
        s = _state()
        details = {"input_token_details": {"cache_read": 300, "cache_creation": 20}}
        s.add_llm_usage(10, 5, provider="anthropic", model="claude-3-5-sonnet", token_details=details)
        s.add_llm_usage(10, 5, provider="anthropic", model="claude-3-5-sonnet", token_details=details)
        usage = s.get_total_llm_usage()
        assert usage["cache_read_tokens"] == 600
        assert usage["cache_creation_tokens"] == 40

    def test_cache_reads_lower_the_run_cost(self, monkeypatch):
        import app.core.config.llm_pricing as llm_pricing

        monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})
        details = {"input_token_details": {"cache_read": 900, "cache_creation": 0}}
        cached = _state()
        cached.add_llm_usage(1000, 0, provider="anthropic", model="claude-3-5-sonnet", token_details=details)
        plain = _state()
        plain.add_llm_usage(1000, 0, provider="anthropic", model="claude-3-5-sonnet")
        assert cached.get_total_llm_usage()["cost_usd"] < plain.get_total_llm_usage()["cost_usd"]


class TestPlatformWithholdInTotals:

    async def _merge_one_call(self) -> WorkflowState:
        s = _state()
        with _caching_provider_injector():
            await merge_llm_usage_from_result(s, {"llm_usage": [{"input_tokens": 10, "output_tokens": 5}]}, "n1", "p1")
        return s

    @pytest.mark.asyncio
    async def test_flag_off_keeps_cache_fields_out_of_the_totals(self, monkeypatch):
        monkeypatch.setattr(settings, "PROMPT_CACHING_FEATURE_ENABLED", False)
        s = await self._merge_one_call()
        usage = s.get_total_llm_usage()

        assert s.llm_usage[0]["prompt_caching_enabled"] is False
        assert "cache_read_tokens" not in usage and "cache_creation_tokens" not in usage

    @pytest.mark.asyncio
    async def test_flag_on_restores_the_zeroed_cache_fields(self, monkeypatch):
        monkeypatch.setattr(settings, "PROMPT_CACHING_FEATURE_ENABLED", True)
        s = await self._merge_one_call()
        usage = s.get_total_llm_usage()

        assert s.llm_usage[0]["prompt_caching_enabled"] is True
        assert usage["cache_read_tokens"] == 0 and usage["cache_creation_tokens"] == 0


class TestFormatIncludesExecutionId:
    def test_execution_id_present_and_matches(self):
        s = _state()
        response = s.format_state_as_response()
        assert response["execution_id"] == s.execution_id
        assert isinstance(s.execution_id, str) and s.execution_id


class TestUpdateNodesDoesNotMergeUsage:
    def test_child_usage_not_merged_by_update_nodes(self):
        parent = _state()
        parent.add_llm_usage(1, 1, node_id="parent")

        child = _state()
        child.add_llm_usage(2, 2, node_id="child")

        parent.update_nodes_from_another_state(child)

        assert len(parent.llm_usage) == 1
        assert parent.llm_usage[0]["node_id"] == "parent"

    def test_sink_semantics_append(self):
        parent = _state()
        parent.add_llm_usage(1, 1, node_id="parent")
        child = _state()
        child.add_llm_usage(2, 2, node_id="child")
        parent.llm_usage.extend(child.llm_usage)
        assert [e["node_id"] for e in parent.llm_usage] == ["parent", "child"]
