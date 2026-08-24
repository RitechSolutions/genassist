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


class TestAnnotateNodeExecution:
    def test_it_attaches_to_an_existing_entry(self):
        state = _run(with_diagnostics=False)
        state.annotate_node_execution("ok", "prompt_caching", _APPLIED)

        assert state.node_execution_status["ok"]["prompt_caching"] == _APPLIED

    def test_it_is_a_no_op_for_a_node_that_never_ran(self):
        state = _run(with_diagnostics=False)
        state.annotate_node_execution("never-ran", "prompt_caching", _APPLIED)

        assert set(state.node_execution_status) == {"ok", "bad"}


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


@pytest.mark.parametrize("entry_annotated", [True, False], ids=["annotated", "plain"])
class TestOwnEntryAnnotationSurvivesTheSubFlowMerge:
    def test_entries_merge_wholesale(self, entry_annotated):
        parent = _state()
        child = _run(with_diagnostics=False)
        if entry_annotated:
            child.annotate_node_execution("ok", "prompt_caching", _APPLIED)

        parent.update_nodes_from_another_state(child)

        assert ("prompt_caching" in parent.node_execution_status["ok"]) is entry_annotated
