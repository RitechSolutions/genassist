"""The propagated sub-agent diagnostics collection must stay invisible to every
operational consumer of a run: metrics, failed nodes, and the state's wire shape"""

import pytest

from app.modules.workflow.engine.workflow_state import WorkflowState

WF = {"config": {"id": "wf-1"}, "nodes": [], "edges": []}
THREAD = "11111111-1111-1111-1111-111111111111"

_APPLIED = {"requested": True, "applied": True, "reason": None}
_WITHHELD = {"requested": True, "applied": False, "reason": "unsupported_mode"}


def _state() -> WorkflowState:
    return WorkflowState(workflow=WF, thread_id=THREAD, initial_values={"message": "hi"})


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
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        state = _run(with_diagnostics=False)
        diagnostics.record(state, "ok", applied=True)

        assert state.prompt_caching_diagnostics == {"ok": _APPLIED}
        assert "prompt_caching" not in state.node_execution_status["ok"]

    def test_a_node_that_never_ran_still_records(self):
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        state = _run(with_diagnostics=False)
        diagnostics.record(state, "never-ran", applied=False, reason="unsupported_mode")

        assert state.prompt_caching_diagnostics == {"never-ran": _WITHHELD}
        assert set(state.node_execution_status) == {"ok", "bad"}


class TestDelegationTurnsMergeIntoOneEntry:

    def test_one_applied_turn_marks_the_node_applied(self):
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        state = _state()
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record(state, "agent", applied=False, reason="unsupported_mode")

        assert state.prompt_caching_diagnostics == {"agent": _APPLIED}

    def test_observed_counts_survive_the_next_turns_re_record(self):
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        state = _state()
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record_observed_cache_tokens(state, "agent", [{"token_details": {"cache_read": 900}}])
        diagnostics.record(state, "agent", applied=True)

        assert state.prompt_caching_diagnostics["agent"] == {
            **_APPLIED,
            "cache_read_tokens": 900,
            "cache_creation_tokens": 0,
        }

    def test_observed_counts_accumulate_across_turns(self):
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        state = _state()
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record_observed_cache_tokens(
            state, "agent", [{"token_details": {"cache_read": 900, "cache_creation": 100}}]
        )
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record_observed_cache_tokens(state, "agent", [{"token_details": {"cache_read": 50}}])

        assert state.prompt_caching_diagnostics["agent"] == {
            **_APPLIED,
            "cache_read_tokens": 950,
            "cache_creation_tokens": 100,
        }

    def test_a_turn_with_no_usage_keeps_earlier_counts(self):
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        state = _state()
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record_observed_cache_tokens(state, "agent", [{"token_details": {"cache_read": 900}}])
        diagnostics.record(state, "agent", applied=True)
        diagnostics.record_observed_cache_tokens(state, "agent", [])

        assert state.prompt_caching_diagnostics["agent"]["cache_read_tokens"] == 900


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
        from app.modules.workflow.engine import prompt_cache_diagnostics as diagnostics

        parent = _state()
        child = _run(with_diagnostics=False)
        diagnostics.record(child, "ok", applied=True)

        parent.update_nodes_from_another_state(child)

        assert parent.prompt_caching_diagnostics == {"ok": _APPLIED}
