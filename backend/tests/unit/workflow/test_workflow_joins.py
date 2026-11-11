import pytest

from app.modules.workflow.engine.workflow_engine import WorkflowEngine


def _edge(source, target, source_handle="output", target_handle="input"):
    return {"source": source, "target": target, "sourceHandle": source_handle, "targetHandle": target_handle}


def _template(node_id, template=None):
    return {"id": node_id, "type": "templateNode", "data": {"name": node_id, "template": template or node_id}}


def _merger(**data):
    return {"id": "merge", "type": "aggregatorNode", "data": {"name": "merge", "aggregationStrategy": "list", **data}}


def _fan_in(*branches, merge=None):
    nodes = [{"id": "in", "type": "chatInputNode", "data": {"name": "Start"}}]
    edges = []
    for branch in branches:
        nodes += [_template(node_id) for node_id in branch]
        edges += [_edge(a, b) for a, b in zip(("in", *branch), (*branch, "merge"))]
    nodes += [merge or _merger(), _template("after"), {"id": "out", "type": "chatOutputNode", "data": {"name": "Finish"}}]
    edges += [_edge("merge", "after"), _edge("after", "out")]
    return {"id": "wf1", "config": {"id": "wf1"}, "nodes": nodes, "edges": edges}


async def _run(workflow):
    return await WorkflowEngine(workflow).execute_from_node(input_data={"message": "go"}, persist=False)


def _merged(output):
    return output["aggregated_outputs"]["outputs"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("branches", "merged"),
    [((("b",), ("c",)), ["b", "c"]), ((("b",), ("c",), ("d",)), ["b", "c", "d"])],
)
async def test_a_merger_fed_by_parallel_branches_runs_once_with_every_branch(branches, merged):
    state = await _run(_fan_in(*branches))
    assert (state.execution_path.count("merge"), state.execution_path.count("after")) == (1, 1)
    assert _merged(state.node_outputs["merge"]) == merged


@pytest.mark.asyncio
async def test_a_merger_waits_for_the_longer_branch_and_runs_once():
    state = await _run(_fan_in(("b",), ("c", "c2")))
    assert (state.execution_path.count("merge"), state.execution_path.count("after")) == (1, 1)
    assert _merged(state.node_outputs["merge"]) == ["b", "c2"]


@pytest.mark.asyncio
async def test_a_merger_that_does_not_wait_for_every_branch_runs_once():
    state = await _run(_fan_in(("b",), ("c",), merge=_merger(requireAllInputs=False)))
    assert (state.execution_path.count("merge"), state.execution_path.count("after")) == (1, 1)


@pytest.mark.asyncio
async def test_a_deactivated_join_forwards_once():
    merge = _template("merge")
    merge["data"]["deactivated"] = True
    state = await _run(_fan_in(("b",), ("c",), merge=merge))
    assert (state.execution_path.count("merge"), state.execution_path.count("after")) == (1, 1)


@pytest.mark.asyncio
async def test_a_join_inside_a_loop_body_runs_once_per_pass():
    workflow = {
        "id": "wf1",
        "config": {"id": "wf1"},
        "nodes": [
            {"id": "in", "type": "chatInputNode", "data": {"name": "Start"}},
            {"id": "loop", "type": "loopNode", "data": {"name": "loop", "mode": "forEach", "items": "[1, 2, 3]"}},
            _template("left", "L{{source.item}}"),
            _template("right", "R{{source.item}}"),
            _merger(),
            _template("after"),
            {"id": "out", "type": "chatOutputNode", "data": {"name": "Finish"}},
        ],
        "edges": [
            _edge("in", "loop"),
            _edge("loop", "left", "output_loop"),
            _edge("loop", "right", "output_loop"),
            _edge("left", "merge"),
            _edge("right", "merge"),
            _edge("merge", "loop", target_handle="input_loop"),
            _edge("loop", "after", "output_done"),
            _edge("after", "out"),
        ],
    }
    state = await _run(workflow)
    assert state.execution_path.count("merge") == 3
    assert [_merged(r) for r in state.node_outputs["loop"]["results"]] == [["L1", "R1"], ["L2", "R2"], ["L3", "R3"]]
