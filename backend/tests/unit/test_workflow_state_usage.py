"""WorkflowState LLM-usage plumbing (correlation id + sink semantics) and the
prompt-caching diagnostics collection, which must stay invisible to every
operational consumer of a run: metrics, failed nodes, and the state's wire shape"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics
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

    def test_a_cache_bucket_with_no_rate_leaves_the_run_cost_partial(self, monkeypatch):
        import app.core.config.llm_pricing as llm_pricing

        monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})
        s = _state()
        s.add_llm_usage(
            7,
            20,
            provider="bedrock",
            model="arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/nova-tuned",
            token_details={"input_token_details": {"cache_read": 3697}},
        )
        s.add_llm_usage(1000, 0, provider="anthropic", model="claude-3-5-sonnet")

        usage = s.get_total_llm_usage()
        assert usage["cost_is_partial"] is True
        assert usage["cost_usd"] == round(1000 / 1000 * 0.003, 6), "only the priced call is counted"

    def test_a_fully_priced_run_is_not_partial(self, monkeypatch):
        import app.core.config.llm_pricing as llm_pricing

        monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})
        s = _state()
        s.add_llm_usage(1000, 0, provider="anthropic", model="claude-3-5-sonnet")

        assert s.get_total_llm_usage()["cost_is_partial"] is False


class TestTheNodeRequestDrivesTheTotals:

    async def _merge_one_call(self, requested: bool) -> WorkflowState:
        s = _state()
        with _caching_provider_injector():
            await merge_llm_usage_from_result(
                s, {"llm_usage": [{"input_tokens": 10, "output_tokens": 5}]}, "n1", "p1", requested
            )
        return s

    @pytest.mark.asyncio
    async def test_an_unrequested_run_keeps_cache_fields_out_of_the_totals(self):
        s = await self._merge_one_call(False)
        usage = s.get_total_llm_usage()

        assert s.llm_usage[0]["prompt_caching_enabled"] is False
        assert "cache_read_tokens" not in usage and "cache_creation_tokens" not in usage

    @pytest.mark.asyncio
    async def test_a_requested_run_reports_the_zeroed_cache_fields(self):
        s = await self._merge_one_call(True)
        usage = s.get_total_llm_usage()

        assert s.llm_usage[0]["prompt_caching_enabled"] is True
        assert usage["cache_read_tokens"] == 0 and usage["cache_creation_tokens"] == 0


class TestFormatIncludesExecutionId:
    def test_execution_id_present_and_matches(self):
        s = _state()
        response = s.format_state_as_response()
        assert response["execution_id"] == s.execution_id
        assert isinstance(s.execution_id, str) and s.execution_id


class TestTheRunCostNeverPassesOffASubtotal:

    UNPRICED_MODEL = "arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/nova-tuned"

    @pytest.fixture(autouse=True)
    def _no_db_rates(self, monkeypatch):
        import app.core.config.llm_pricing as llm_pricing

        monkeypatch.setattr(llm_pricing, "get_db_pricing_nested", lambda tenant: {})

    def _unpriced_call(self, s: WorkflowState) -> None:
        s.add_llm_usage(
            7,
            20,
            provider="bedrock",
            model=self.UNPRICED_MODEL,
            token_details={"input_token_details": {"cache_read": 3697}},
        )

    def test_a_fully_priced_run_reports_its_total(self):
        s = _state()
        s.add_llm_usage(1000, 0, provider="anthropic", model="claude-3-5-sonnet")

        response = s.format_state_as_response()
        assert response["token_usage"]["cost_is_partial"] is False
        assert response["cost_usd"] == round(1000 / 1000 * 0.003, 6)

    def test_a_mixed_run_reports_no_total_but_keeps_the_subtotal(self):
        s = _state()
        s.add_llm_usage(1000, 0, provider="anthropic", model="claude-3-5-sonnet")
        self._unpriced_call(s)

        response = s.format_state_as_response()
        assert response["cost_usd"] is None
        assert response["token_usage"]["cost_is_partial"] is True
        assert response["token_usage"]["cost_usd"] == round(1000 / 1000 * 0.003, 6)

    def test_an_entirely_unpriced_run_is_not_reported_as_free(self):
        s = _state()
        self._unpriced_call(s)

        response = s.format_state_as_response()
        assert response["cost_usd"] is None
        assert response["token_usage"]["cost_is_partial"] is True

    def test_a_run_with_no_llm_calls_still_costs_zero(self):
        response = _state().format_state_as_response()
        assert response["cost_usd"] == 0.0
        assert response["token_usage"]["cost_is_partial"] is False


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


_APPLIED = {"requested": True, "applied": True}
_WITHHELD = {"requested": True, "applied": False}


def _run(*, with_diagnostics: bool) -> WorkflowState:
    state = _state()
    state.node_execution_status = {
        "ok": {"type": "llmModelNode", "name": "LLM", "status": "success", "startTime": 100, "endTime": 150},
        "bad": {"type": "apiNode", "name": "API", "status": "failed", "startTime": 150, "endTime": 200,
                "error": "boom"},
    }
    if with_diagnostics:
        state.prompt_caching_diagnostics = {"child": _WITHHELD, "grandchild": _APPLIED}
    return state


class TestMetricsAndFailuresAreUnchanged:
    def test_performance_metrics_are_byte_identical(self):
        plain, annotated = _run(with_diagnostics=False), _run(with_diagnostics=True)

        plain._update_performance_metrics()
        annotated._update_performance_metrics()

        assert annotated.performance_metrics == plain.performance_metrics

    def test_the_success_rate_denominator_is_untouched(self):
        annotated = _run(with_diagnostics=True)
        annotated._update_performance_metrics()

        assert annotated.performance_metrics["successRate"] == 50.0

    def test_the_failed_node_list_is_untouched(self):
        plain, annotated = _run(with_diagnostics=False), _run(with_diagnostics=True)

        assert annotated._collect_failed_nodes() == plain._collect_failed_nodes()
        assert [n["node_id"] for n in annotated._collect_failed_nodes()] == ["bad"]


class TestWireShape:
    def test_the_key_is_absent_when_nothing_was_collected(self):
        assert "promptCachingDiagnostics" not in _run(with_diagnostics=False).get_full_state()

    def test_a_run_without_diagnostics_serializes_identically(self):
        plain, annotated = _run(with_diagnostics=False), _run(with_diagnostics=True)

        assert set(annotated.get_full_state()) - set(plain.get_full_state()) == {"promptCachingDiagnostics"}

    def test_the_collection_rides_its_own_key(self):
        full = _run(with_diagnostics=True).get_full_state()

        assert full["promptCachingDiagnostics"] == {"child": _WITHHELD, "grandchild": _APPLIED}
        assert set(full["nodeExecutionStatus"]) == {"ok", "bad"}


class TestRecordWritesTheSingleStore:
    def test_a_recorded_diagnostic_lands_in_the_collection_not_the_entry(self):
        state = _run(with_diagnostics=False)
        diagnostics.record(state, "ok", applied=True)

        assert state.prompt_caching_diagnostics == {"ok": _APPLIED}
        assert "prompt_caching" not in state.node_execution_status["ok"]

    def test_a_node_that_never_ran_still_records(self):
        state = _run(with_diagnostics=False)
        diagnostics.record(state, "never-ran", applied=False, reason="unsupported_mode")

        assert state.prompt_caching_diagnostics == {"never-ran": _WITHHELD}
        assert set(state.node_execution_status) == {"ok", "bad"}


class TestDelegationTurnsMergeIntoOneEntry:

    def test_one_applied_turn_marks_the_node_applied(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record(state, "agent", applied=False, reason="unsupported_mode")

        assert state.prompt_caching_diagnostics == {"agent": _APPLIED}

    def test_a_re_record_keeps_the_entry_flag_only(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record(state, "agent", applied=True)

        assert state.prompt_caching_diagnostics == {"agent": _APPLIED}


class TestSerializedCacheTokensComeFromUsage:

    @staticmethod
    def _serialized(state) -> dict:
        return state.get_full_state()["promptCachingDiagnostics"]["agent"]

    def test_an_applied_run_serializes_what_the_provider_reported(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)
        state.add_llm_usage(
            5, 2, node_id="agent", prompt_caching_enabled=True,
            token_details={"cache_read": 900, "cache_creation": 100},
        )
        state.add_llm_usage(
            5, 2, node_id="agent", prompt_caching_enabled=True, token_details={"cache_read": 50}
        )

        assert self._serialized(state) == {
            **_APPLIED,
            "cache_read_tokens": 950,
            "cache_creation_tokens": 100,
        }

    def test_zero_activity_is_stamped_as_zero_not_left_absent(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)
        state.add_llm_usage(5, 2, node_id="agent", prompt_caching_enabled=True)

        serialized = self._serialized(state)
        assert serialized["cache_read_tokens"] == 0
        assert serialized["cache_creation_tokens"] == 0

    def test_a_run_with_no_usage_stays_unstamped(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)

        assert self._serialized(state) == _APPLIED

    def test_a_placeholder_with_no_provider_report_never_stamps_zeros(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)
        state.add_llm_usage(
            0, 0, node_id="agent", prompt_caching_enabled=True,
            token_details={"usage_metadata_missing": True},
        )

        assert self._serialized(state) == _APPLIED

    def test_a_withheld_entry_never_gains_token_fields(self):
        state = _state()
        diagnostics.record(state, "agent", applied=False, reason="volatile_prompt")
        state.add_llm_usage(
            5, 2, node_id="agent", prompt_caching_enabled=True, token_details={"cache_read": 900}
        )

        assert self._serialized(state) == _WITHHELD

    def test_unflagged_and_other_node_usage_is_ignored(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)
        state.add_llm_usage(5, 2, node_id="agent", token_details={"cache_read": 900})
        state.add_llm_usage(
            5, 2, node_id="other", prompt_caching_enabled=True, token_details={"cache_read": 50}
        )

        assert self._serialized(state) == _APPLIED

    def test_the_stored_collection_stays_flag_only(self):
        state = _state()
        diagnostics.record(state, "agent", applied=True)
        state.add_llm_usage(
            5, 2, node_id="agent", prompt_caching_enabled=True, token_details={"cache_read": 900}
        )
        state.get_full_state()

        assert state.prompt_caching_diagnostics == {"agent": _APPLIED}


class TestCollectionLifecycle:
    def test_a_fresh_state_starts_empty(self):
        assert _state().prompt_caching_diagnostics == {}

    def test_reset_clears_it(self):
        state = _run(with_diagnostics=True)
        state.reset_execution_state()

        assert state.prompt_caching_diagnostics == {}

    def test_a_sub_flow_merge_carries_it_incoming_wins(self):
        parent = _state()
        parent.prompt_caching_diagnostics = {"a": _APPLIED, "b": _APPLIED}
        child = _state()
        child.prompt_caching_diagnostics = {"b": _WITHHELD, "c": _WITHHELD}

        parent.update_nodes_from_another_state(child)

        assert parent.prompt_caching_diagnostics == {"a": _APPLIED, "b": _WITHHELD, "c": _WITHHELD}

    def test_the_merge_still_leaves_usage_alone(self):
        parent, child = _state(), _state()
        parent.add_llm_usage(1, 1, node_id="parent")
        child.add_llm_usage(2, 2, node_id="child")
        child.prompt_caching_diagnostics = {"c": _WITHHELD}

        parent.update_nodes_from_another_state(child)

        assert [e["node_id"] for e in parent.llm_usage] == ["parent"]
        assert parent.prompt_caching_diagnostics == {"c": _WITHHELD}


class TestOwnDiagnosticsSurviveTheSubFlowMerge:
    def test_the_childs_own_recording_reaches_the_parent_collection(self):
        parent = _state()
        child = _run(with_diagnostics=False)
        diagnostics.record(child, "ok", applied=True)

        parent.update_nodes_from_another_state(child)

        assert parent.prompt_caching_diagnostics == {"ok": _APPLIED}
