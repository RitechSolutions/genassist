"""Tests for LoopNode: per-item and repeat-until iteration, what the body and the
Done branch see, limits, failures, nesting and deactivation, all as real engine runs."""

import asyncio

import pytest

from app.core.config.settings import settings
from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import node_failure
from app.modules.workflow.engine.nodes.loop_node import LoopNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine


def _edge(source, target, source_handle="output", target_handle="input"):
    return {"source": source, "target": target, "sourceHandle": source_handle, "targetHandle": target_handle}


def _template(node_id, template):
    return {"id": node_id, "type": "templateNode", "data": {"name": node_id, "template": template}}


def _loop(node_id="loop", **data):
    return {"id": node_id, "type": "loopNode", "data": {"name": node_id, **data}}


def _workflow(loop_data, body=None, extra_nodes=(), extra_edges=()):
    """in → prep → loop ─loop→ body… ─back→ loop ; loop ─done→ after → out"""
    body = body or [_template("work", "did {{source.item}}")]
    nodes = [
        {"id": "in", "type": "chatInputNode", "data": {"name": "Start"}},
        _template("prep", "{{session.message}}"),
        _loop(**loop_data),
        *body,
        _template("after", "{{source.count}} done ({{source.stopped_reason}})"),
        {"id": "out", "type": "chatOutputNode", "data": {"name": "Finish"}},
        *extra_nodes,
    ]
    edges = [
        _edge("in", "prep"),
        _edge("prep", "loop"),
        _edge("loop", body[0]["id"], "output_loop"),
        *[_edge(a["id"], b["id"]) for a, b in zip(body, body[1:])],
        _edge(body[-1]["id"], "loop", target_handle="input_loop"),
        _edge("loop", "after", "output_done"),
        _edge("after", "out"),
        *extra_edges,
    ]
    return {"id": "wf1", "config": {"id": "wf1"}, "nodes": nodes, "edges": edges}


async def _run(workflow, message="go"):
    return await WorkflowEngine(workflow).execute_from_node(input_data={"message": message}, persist=False)


# ---- for each ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_for_each_runs_the_body_once_per_item_and_collects_results_in_order():
    state = await _run(_workflow({"mode": "forEach", "items": '["a", "b", "c"]'}))
    loop = state.node_outputs["loop"]
    assert loop["results"] == ["did a", "did b", "did c"]
    assert (loop["count"], loop["iterations"], loop["total"], loop["skipped"]) == (3, 3, 3, 0)
    assert loop["last"] == "did c"
    assert loop["errors"] == [] and loop["stopped_reason"] == "completed"
    assert "next_nodes" not in loop


@pytest.mark.asyncio
async def test_done_branch_runs_once_after_the_loop_and_provides_the_reply():
    state = await _run(_workflow({"mode": "forEach", "items": '["a", "b"]'}))
    assert state.node_outputs["after"] == "2 done (completed)"
    assert state.execution_path.count("after") == 1
    assert state.format_state_as_response()["output"] == "2 done (completed)"


@pytest.mark.asyncio
async def test_items_come_from_an_upstream_variable():
    workflow = _workflow({"mode": "forEach", "items": "{{source}}"})
    state = await _run(workflow, message='[{"id": 1}, {"id": 2}]')
    assert state.node_outputs["loop"]["count"] == 2


@pytest.mark.asyncio
async def test_iteration_context_is_available_to_every_body_node():
    body = [
        _template("first", "{{source.index}}/{{source.total}} first={{source.is_first}} last={{source.is_last}}"),
        _template("second", "{{source}} item={{node_outputs.loop.item.id}} input={{node_outputs.loop.input}}"),
    ]
    workflow = _workflow({"mode": "forEach", "items": '[{"id": "x"}, {"id": "y"}]'}, body=body)
    state = await _run(workflow)
    assert state.node_outputs["loop"]["results"] == [
        "0/2 first=true last=false item=x input=go",
        "1/2 first=false last=true item=y input=go",
    ]


@pytest.mark.asyncio
async def test_an_object_iterates_as_key_value_entries():
    body = [_template("work", "{{source.item.key}}={{source.item.value}}")]
    state = await _run(_workflow({"mode": "forEach", "items": '{"a": 1, "b": 2}'}, body=body))
    assert state.node_outputs["loop"]["results"] == ["a=1", "b=2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("items", ["[]", "", "null"])
async def test_an_empty_list_skips_the_body_and_still_continues_from_done(items):
    state = await _run(_workflow({"mode": "forEach", "items": items}))
    assert "work" not in state.node_outputs
    assert state.node_outputs["loop"]["iterations"] == 0
    assert state.node_outputs["after"] == "0 done (completed)"


@pytest.mark.asyncio
@pytest.mark.parametrize("items", ["true", "3.5", "-1"])
async def test_items_that_cannot_be_iterated_fail_the_node_and_stop_the_branch(items):
    state = await _run(_workflow({"mode": "forEach", "items": items}))
    assert state.node_execution_status["loop"]["status"] == "failed"
    assert "work" not in state.node_outputs and "after" not in state.node_outputs
    assert state.format_state_as_response()["has_failures"] is True


@pytest.mark.asyncio
async def test_a_filter_in_the_body_skips_the_item_without_reusing_the_previous_result():
    body = [
        {"id": "gate", "type": "filterNode", "data": {"name": "gate", "field": "{{source.item}}", "operator": "not_equal", "value": "b"}},
        _template("work", "did {{source.item}}"),
    ]
    state = await _run(_workflow({"mode": "forEach", "items": '["a", "b", "c"]'}, body=body))
    loop = state.node_outputs["loop"]
    assert loop["results"] == ["did a", "did c"]
    assert (loop["iterations"], loop["skipped"]) == (3, 1)


@pytest.mark.asyncio
async def test_for_each_stops_early_when_the_stop_condition_holds():
    loop_data = {"mode": "forEach", "items": '["a", "b", "c"]', "stopField": "{{node_outputs.work}}", "stopOperator": "equal", "stopValue": "did b"}
    state = await _run(_workflow(loop_data))
    loop = state.node_outputs["loop"]
    assert loop["results"] == ["did a", "did b"]
    assert loop["stopped_reason"] == "condition"


@pytest.mark.asyncio
async def test_more_items_than_max_iterations_are_cut_off_and_reported():
    state = await _run(_workflow({"mode": "forEach", "items": "[1, 2, 3, 4, 5]", "maxIterations": 2}))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["total"], loop["stopped_reason"]) == (2, 5, "max_iterations")


@pytest.mark.asyncio
async def test_without_a_back_edge_the_last_body_node_is_the_result():
    workflow = _workflow({"mode": "forEach", "items": '["a", "b"]'})
    workflow["edges"] = [e for e in workflow["edges"] if e["targetHandle"] != "input_loop"]
    state = await _run(workflow)
    assert state.node_outputs["loop"]["results"] == ["did a", "did b"]


@pytest.mark.asyncio
async def test_a_loop_without_a_body_reports_the_list_size_and_continues():
    workflow = _workflow({"mode": "forEach", "items": "[1, 2, 3]"})
    workflow["edges"] = [e for e in workflow["edges"] if "work" not in (e["source"], e["target"])]
    state = await _run(workflow)
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["total"], loop["stopped_reason"]) == (0, 3, "no_body")
    assert "after" in state.node_outputs


# ---- repeat until -----------------------------------------------------------


@pytest.mark.asyncio
async def test_repeat_until_stops_as_soon_as_the_condition_holds():
    loop_data = {"mode": "repeatUntil", "maxIterations": 10, "stopField": "{{node_outputs.work}}", "stopOperator": "ends_with", "stopValue": "#3"}
    body = [_template("work", "attempt #{{source.iteration}}")]
    state = await _run(_workflow(loop_data, body=body))
    loop = state.node_outputs["loop"]
    assert loop["results"] == ["attempt #1", "attempt #2", "attempt #3"]
    assert (loop["last"], loop["stopped_reason"]) == ("attempt #3", "condition")


@pytest.mark.asyncio
async def test_repeat_until_gives_the_body_the_previous_result_and_the_original_input():
    loop_data = {"mode": "repeatUntil", "maxIterations": 3}
    body = [_template("work", "[{{source.previous}}]+{{source.input}}")]
    state = await _run(_workflow(loop_data, body=body), message="seed")
    assert state.node_outputs["loop"]["results"] == ["[null]+seed", "[[null]+seed]+seed", "[[[null]+seed]+seed]+seed"]
    # No stop condition: running all the passes is the expected outcome.
    assert state.node_outputs["loop"]["stopped_reason"] == "completed"


@pytest.mark.asyncio
async def test_repeat_until_reports_when_the_condition_never_held():
    loop_data = {"mode": "repeatUntil", "maxIterations": 4, "stopField": "{{node_outputs.work}}", "stopOperator": "equal", "stopValue": "never"}
    state = await _run(_workflow(loop_data))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["stopped_reason"]) == (4, "max_iterations")
    assert "after" in state.node_outputs


@pytest.mark.asyncio
async def test_a_broken_stop_condition_does_not_stop_the_loop():
    loop_data = {"mode": "repeatUntil", "maxIterations": 2, "stopField": "{{node_outputs.work}}", "stopOperator": "regex", "stopValue": "(unclosed"}
    state = await _run(_workflow(loop_data))
    assert state.node_outputs["loop"]["iterations"] == 2


def test_max_iterations_defaults_per_mode_and_is_capped():
    assert LoopNode._max_iterations(None, "forEach", 1000) == 100
    assert LoopNode._max_iterations("", "repeatUntil", 1000) == 5
    assert LoopNode._max_iterations(0, "repeatUntil", 1000) == 5
    assert LoopNode._max_iterations("7", "forEach", 1000) == 7
    assert LoopNode._max_iterations(50_000, "forEach", 1000) == 1000


# ---- failures ---------------------------------------------------------------


class _FailsOnBad(BaseNode):
    async def process(self, config):
        if config.get("value") == "bad":
            return node_failure("could not process bad", output="failed bad")
        return f"ok {config.get('value')}"


@pytest.fixture
def failing_node_type(monkeypatch):
    WorkflowEngine._initialize_node_registry()
    monkeypatch.setitem(WorkflowEngine._node_registry, "failsOnBadNode", _FailsOnBad)
    return {"id": "work", "type": "failsOnBadNode", "data": {"name": "Worker", "value": "{{source.item}}"}}


@pytest.mark.asyncio
async def test_a_failing_pass_stops_the_loop_by_default_and_done_still_runs(failing_node_type):
    state = await _run(_workflow({"mode": "forEach", "items": '["a", "bad", "c"]'}, body=[failing_node_type]))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["stopped_reason"]) == (2, "error")
    assert loop["errors"] == [{"index": 1, "node_id": "work", "node_name": "Worker", "error": "could not process bad"}]
    assert loop["results"] == ["ok a"] and loop["failed"] == 1
    assert state.node_outputs["after"] == "1 done (error)"


@pytest.mark.asyncio
async def test_on_error_continue_finishes_the_list_and_collects_the_errors(failing_node_type):
    loop_data = {"mode": "forEach", "items": '["a", "bad", "c", "bad"]', "onError": "continue"}
    state = await _run(_workflow(loop_data, body=[failing_node_type]))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["stopped_reason"]) == (4, "completed")
    assert [e["index"] for e in loop["errors"]] == [1, 3]
    # What a failing pass left behind is reported in errors, not as a result.
    assert loop["results"] == ["ok a", "ok c"]
    assert (loop["count"], loop["failed"], loop["skipped"]) == (2, 2, 0)


# ---- limits and trace -------------------------------------------------------


@pytest.mark.asyncio
async def test_the_run_wide_iteration_budget_stops_the_loop(monkeypatch):
    monkeypatch.setattr(settings, "WORKFLOW_LOOP_MAX_TOTAL_ITERATIONS", 3)
    state = await _run(_workflow({"mode": "forEach", "items": "[1, 2, 3, 4, 5]"}))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["stopped_reason"]) == (3, "budget")


@pytest.mark.asyncio
async def test_the_server_cap_bounds_a_single_loop(monkeypatch):
    monkeypatch.setattr(settings, "WORKFLOW_LOOP_MAX_ITERATIONS", 2)
    state = await _run(_workflow({"mode": "forEach", "items": "[1, 2, 3]", "maxIterations": 500}))
    assert state.node_outputs["loop"]["iterations"] == 2


@pytest.mark.asyncio
async def test_the_run_trace_keeps_a_bounded_number_of_earlier_passes():
    items = "[" + ", ".join(str(i) for i in range(30)) + "]"
    state = await _run(_workflow({"mode": "forEach", "items": items}))
    archived = [key for key in state.node_execution_status if key.startswith("work_")]
    assert len(archived) == 20
    assert state.node_execution_status["work"]["output"] == "did 29"
    assert state.node_execution_status["work"]["run"] == 30
    assert "run" not in state.node_execution_status["prep"]
    assert state.active_loops == []


@pytest.mark.asyncio
async def test_a_huge_count_is_never_built_into_a_list():
    state = await _run(_workflow({"mode": "forEach", "items": "1e12", "maxIterations": 3}))
    loop = state.node_outputs["loop"]
    assert loop["results"] == ["did 0", "did 1", "did 2"]
    assert (loop["total_items"], loop["total"], loop["stopped_reason"]) == (10**12, 10**12, "max_iterations")


@pytest.mark.asyncio
async def test_a_huge_count_in_huge_batches_is_bounded_by_the_server_cap(monkeypatch):
    monkeypatch.setattr(settings, "WORKFLOW_LOOP_MAX_ITERATIONS", 4)
    body = [_template("work", "{{source.item}}")]
    state = await _run(_workflow({"mode": "forEach", "items": "1e12", "batchSize": 10**12, "maxIterations": 1}, body=body))
    assert state.node_outputs["loop"]["results"] == ["[0, 1, 2, 3]"]


def test_a_count_is_lazy_and_must_be_a_finite_whole_number():
    assert LoopNode._parse_items("1e12") == range(10**12)
    assert LoopNode._parse_items(3) == range(3)
    for bad in ("Infinity", "NaN", "1e400", "-1", "2.5"):
        with pytest.raises(ValueError, match="whole number"):
            LoopNode._parse_items(bad)


# ---- nesting, deactivation --------------------------------------------------


def _nested_failing_workflow(inner_on_error, outer_items='[["a", "bad", "c"], ["d"]]', **outer):
    """outer loop → inner loop (→ work → back) ─done→ row → back to the outer loop"""
    body = [
        _loop("inner", mode="forEach", items="{{source.item}}", onError=inner_on_error),
        {"id": "work", "type": "failsOnBadNode", "data": {"name": "Worker", "value": "{{source.item}}"}},
        _template("row", "{{source.count}}"),
    ]
    workflow = _workflow({"mode": "forEach", "items": outer_items, **outer}, body=body)
    workflow["edges"] = [e for e in workflow["edges"] if (e["source"], e["target"]) not in {("inner", "work"), ("work", "row")}]
    workflow["edges"] += [
        _edge("inner", "work", "output_loop"),
        _edge("work", "inner", target_handle="input_loop"),
        _edge("inner", "row", "output_done"),
    ]
    return workflow


@pytest.mark.asyncio
async def test_a_failure_the_inner_loop_carried_on_past_does_not_fail_the_outer_pass(failing_node_type):
    state = await _run(_nested_failing_workflow("continue"))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["stopped_reason"]) == (2, "completed")
    assert (loop["failed"], loop["errors"]) == (0, [])
    assert loop["results"] == ["2", "1"]


@pytest.mark.asyncio
async def test_a_failure_that_stopped_the_inner_loop_fails_the_outer_pass(failing_node_type):
    state = await _run(_nested_failing_workflow("stop"))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["stopped_reason"]) == (1, "error")
    assert loop["errors"] == [{"index": 0, "node_id": "work", "node_name": "Worker", "error": "could not process bad"}]

    state = await _run(_nested_failing_workflow("stop", onError="continue"))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["failed"], loop["stopped_reason"]) == (2, 1, "completed")
    assert loop["results"] == ["1"]


@pytest.mark.asyncio
async def test_nested_loops_run_the_inner_loop_once_per_outer_item():
    body = [
        _loop("inner", mode="forEach", items="{{source.item}}"),
        _template("cell", "<{{source.item}}>"),
        _template("row", "{{source.results}}"),
    ]
    workflow = _workflow({"mode": "forEach", "items": "[[1, 2], [3]]"}, body=body)
    # inner: loop → cell → back to inner; inner done → row → back to the outer loop
    workflow["edges"] = [e for e in workflow["edges"] if (e["source"], e["target"]) not in {("inner", "cell"), ("cell", "row")}]
    workflow["edges"] += [
        _edge("inner", "cell", "output_loop"),
        _edge("cell", "inner", target_handle="input_loop"),
        _edge("inner", "row", "output_done"),
    ]
    state = await _run(workflow)
    assert state.node_outputs["loop"]["results"] == ['["<1>", "<2>"]', '["<3>"]']
    assert state.loop_iterations_total == 2 + 3


@pytest.mark.asyncio
async def test_a_deactivated_loop_skips_its_body_and_continues_from_done():
    workflow = _workflow({"mode": "forEach", "items": '["a"]', "deactivated": True})
    workflow["nodes"][4] = _template("after", "after got: {{source}}")
    state = await _run(workflow)
    assert "work" not in state.node_outputs
    assert state.node_outputs["after"] == "after got: go"


@pytest.mark.asyncio
async def test_parallel_body_branches_are_merged_from_this_pass_only():
    body = [
        _template("left", "L{{source.item}}"),
        _template("right", "R{{source.item}}"),
        {"id": "merge", "type": "aggregatorNode", "data": {"name": "merge", "aggregationStrategy": "list"}},
    ]
    workflow = _workflow({"mode": "forEach", "items": "[1, 2]"}, body=body)
    workflow["edges"] = [e for e in workflow["edges"] if (e["source"], e["target"]) != ("left", "right")]
    workflow["edges"] += [_edge("loop", "right", "output_loop"), _edge("left", "merge")]
    state = await _run(workflow)
    results = state.node_outputs["loop"]["results"]
    assert len(results) == 2
    assert [sorted(r["aggregated_outputs"]["outputs"]) for r in results] == [["L1", "R1"], ["L2", "R2"]]


@pytest.mark.asyncio
async def test_source_in_the_stop_condition_is_the_loops_own_input():
    loop_data = {"mode": "repeatUntil", "maxIterations": 4, "stopField": "{{source}}", "stopOperator": "equal", "stopValue": "go"}
    state = await _run(_workflow(loop_data))
    assert (state.node_outputs["loop"]["iterations"], state.node_outputs["loop"]["stopped_reason"]) == (1, "condition")


# ---- Done next to a parallel branch -----------------------------------------


class _TakesAWhile(BaseNode):
    """Yields to the event loop, so whatever runs in parallel finishes first."""

    async def process(self, config):
        await asyncio.sleep(0.01)
        return f"did {config.get('value')}"


@pytest.fixture
def slow_node(monkeypatch):
    WorkflowEngine._initialize_node_registry()
    monkeypatch.setitem(WorkflowEngine._node_registry, "takesAWhileNode", _TakesAWhile)

    def build(node_id, value):
        return {"id": node_id, "type": "takesAWhileNode", "data": {"name": node_id, "value": value}}

    return build


def _done_joins_a_parallel_branch(work, side, after):
    """prep → loop ─done→ after, and prep → side → after: ``after`` waits for both."""
    workflow = _workflow(
        {"mode": "forEach", "items": '["a", "b"]'},
        body=[work],
        extra_nodes=[side],
        extra_edges=[_edge("prep", "side"), _edge("side", "after")],
    )
    workflow["nodes"][4] = after
    return workflow


@pytest.mark.asyncio
@pytest.mark.parametrize("slow", ["work", "side"])
async def test_a_node_fed_by_done_and_a_parallel_branch_runs_once_with_the_loops_result(slow_node, slow):
    nodes = {"work": _template("work", "did {{source.item}}"), "side": _template("side", "did side")}
    nodes[slow] = slow_node(slow, "{{source.item}}" if slow == "work" else "side")
    after = _template("after", "{{source.loop.results}} + {{source.side}}")
    state = await _run(_done_joins_a_parallel_branch(nodes["work"], nodes["side"], after))
    assert state.execution_path.count("after") == 1
    assert state.node_outputs["after"] == '["did a", "did b"] + did side'


@pytest.mark.asyncio
async def test_an_aggregator_that_does_not_wait_leaves_a_running_loop_out(slow_node):
    after = {
        "id": "after",
        "type": "aggregatorNode",
        "data": {"name": "after", "aggregationStrategy": "list", "requireAllInputs": False},
    }
    workflow = _done_joins_a_parallel_branch(slow_node("work", "{{source.item}}"), _template("side", "did side"), after)
    state = await _run(workflow)
    first_run = state.node_execution_status.get("after_0") or state.node_execution_status["after"]
    assert first_run["output"]["aggregated_outputs"]["outputs"] == ["did side"]


@pytest.mark.asyncio
async def test_a_node_fed_by_an_inner_loops_done_runs_once_per_outer_pass(slow_node):
    body = [
        _loop("inner", mode="forEach", items="{{source.item}}"),
        slow_node("cell", "{{source.item}}"),
        _template("row", "{{source.inner.results}} + {{source.side}}"),
    ]
    workflow = _workflow(
        {"mode": "forEach", "items": "[[1, 2], [3]]"},
        body=body,
        extra_nodes=[_template("side", "side {{source.index}}")],
        extra_edges=[_edge("loop", "side", "output_loop"), _edge("side", "row")],
    )
    # inner: loop → cell → back to inner; inner done → row ← side; row → back to the outer loop
    workflow["edges"] = [e for e in workflow["edges"] if (e["source"], e["target"]) not in {("inner", "cell"), ("cell", "row")}]
    workflow["edges"] += [
        _edge("inner", "cell", "output_loop"),
        _edge("cell", "inner", target_handle="input_loop"),
        _edge("inner", "row", "output_done"),
    ]
    state = await _run(workflow)
    assert state.node_outputs["loop"]["results"] == ['["did 1", "did 2"] + side 0', '["did 3"] + side 1']
    assert state.node_execution_status["row"]["run"] == 2


@pytest.mark.asyncio
async def test_a_loop_that_breaks_mid_pass_leaves_no_pass_data_behind_as_its_output(monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(LoopNode, "_iteration_result", broken)
    state = await _run(_workflow({"mode": "forEach", "items": '["a", "b"]'}))
    assert state.node_execution_status["loop"]["status"] == "failed"
    assert "loop" not in state.node_outputs and "after" not in state.node_outputs
    assert state.execution_path.count("work") == 1
    assert state.active_loops == []


# ---- items, batches ---------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "items, expected",
    [
        ("3", ["did 0", "did 1", "did 2"]),  # a whole number repeats that many times
        ("red, green ,blue", ["did red", "did green", "did blue"]),  # one line: split on commas
        ("red\ngreen\n\nblue", ["did red", "did green", "did blue"]),  # several lines: one item each
        ("single", ["did single"]),
    ],
)
async def test_numbers_and_plain_text_are_accepted_as_items(items, expected):
    state = await _run(_workflow({"mode": "forEach", "items": items}))
    assert state.node_outputs["loop"]["results"] == expected


@pytest.mark.asyncio
async def test_batch_size_gives_each_pass_a_slice_of_the_list():
    state = await _run(_workflow({"mode": "forEach", "items": "[1, 2, 3, 4, 5]", "batchSize": 2}))
    loop = state.node_outputs["loop"]
    assert loop["results"] == ["did [1, 2]", "did [3, 4]", "did [5]"]
    assert (loop["iterations"], loop["total"], loop["total_items"]) == (3, 3, 5)


@pytest.mark.asyncio
async def test_max_iterations_counts_batches():
    state = await _run(_workflow({"mode": "forEach", "items": "[1, 2, 3, 4, 5]", "batchSize": 2, "maxIterations": 2}))
    loop = state.node_outputs["loop"]
    assert loop["results"] == ["did [1, 2]", "did [3, 4]"]
    assert loop["stopped_reason"] == "max_iterations"


# ---- collecting -------------------------------------------------------------


@pytest.mark.asyncio
async def test_collect_last_keeps_only_the_final_result():
    state = await _run(_workflow({"mode": "forEach", "items": '["a", "b", "c"]', "collect": "last"}))
    loop = state.node_outputs["loop"]
    assert (loop["results"], loop["last"], loop["count"]) == (["did c"], "did c", 3)


@pytest.mark.asyncio
async def test_collect_none_returns_counts_only():
    loop_data = {"mode": "repeatUntil", "maxIterations": 3, "collect": "none"}
    body = [_template("work", "[{{source.previous}}]")]
    state = await _run(_workflow(loop_data, body=body))
    loop = state.node_outputs["loop"]
    assert (loop["results"], loop["last"], loop["count"]) == ([], None, 3)
    # The body still sees the previous pass; only the Done output is trimmed.
    assert state.node_outputs["work"] == "[[[null]]]"


@pytest.mark.asyncio
async def test_the_pass_result_is_readable_from_the_loop_itself():
    loop_data = {
        "mode": "repeatUntil",
        "maxIterations": 10,
        "stopField": "{{node_outputs.loop.result}}",
        "stopOperator": "ends_with",
        "stopValue": "#2",
    }
    body = [_template("work", "attempt #{{source.iteration}}")]
    state = await _run(_workflow(loop_data, body=body))
    assert state.node_outputs["loop"]["results"] == ["attempt #1", "attempt #2"]


# ---- delay, time limit ------------------------------------------------------


@pytest.fixture
def sleeps(monkeypatch):
    import asyncio

    waited = []
    real_sleep = asyncio.sleep

    async def fake_sleep(seconds, *args, **kwargs):
        waited.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr("app.modules.workflow.engine.nodes.loop_node.asyncio.sleep", fake_sleep)
    return waited


@pytest.mark.asyncio
async def test_delay_waits_between_passes_but_not_before_the_first(sleeps):
    state = await _run(_workflow({"mode": "forEach", "items": "[1, 2, 3]", "delaySeconds": 1.5}))
    assert state.node_outputs["loop"]["iterations"] == 3
    assert sleeps == [1.5, 1.5]


@pytest.mark.asyncio
async def test_backoff_doubles_the_delay_up_to_the_cap(sleeps):
    loop_data = {"mode": "repeatUntil", "maxIterations": 5, "delaySeconds": 20, "delayBackoff": True}
    await _run(_workflow(loop_data))
    assert sleeps == [20, 40, 60, 60]


@pytest.mark.asyncio
async def test_no_delay_by_default(sleeps):
    await _run(_workflow({"mode": "forEach", "items": "[1, 2, 3]"}))
    assert sleeps == []


@pytest.mark.asyncio
async def test_the_time_limit_stops_the_loop_instead_of_waiting_past_it(sleeps):
    loop_data = {"mode": "forEach", "items": "[1, 2, 3]", "delaySeconds": 30, "timeLimitSeconds": 10}
    state = await _run(_workflow(loop_data))
    loop = state.node_outputs["loop"]
    assert (loop["iterations"], loop["stopped_reason"]) == (1, "timeout")
    assert sleeps == []
    assert "after" in state.node_outputs


def test_numeric_settings_tolerate_text_and_junk():
    assert LoopNode._number("2.5", 0) == 2.5
    assert LoopNode._number("", 7) == 7
    assert LoopNode._number(None, 7) == 7
    assert LoopNode._number("abc", 7) == 7
    assert LoopNode._number(True, 7) == 7
    assert LoopNode._number("nan", 7) == 7
