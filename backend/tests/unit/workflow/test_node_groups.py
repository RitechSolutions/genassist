"""Visual node groups ("groupNode") are editor-only: the engine must drop them so a workflow
runs exactly the same with or without them."""

import copy

import pytest

from app.modules.workflow.engine.workflow_engine import WorkflowEngine, executable_nodes

GROUP = {
    "id": "g1",
    "type": "groupNode",
    "position": {"x": 0, "y": 0},
    "style": {"width": 800, "height": 400},
    "zIndex": -1001,
    "data": {"name": "Payment Processing"},
}


def _workflow(with_input=True, grouped=False):
    nodes = [
        {"id": "prep", "type": "templateNode", "data": {"name": "Prep", "template": "prepared {{session.message}}"}},
        {"id": "next", "type": "templateNode", "data": {"name": "Next", "template": "got: {{source}}"}},
    ]
    edges = [{"source": "prep", "target": "next", "sourceHandle": "output", "targetHandle": "input"}]
    if with_input:
        nodes.insert(0, {"id": "in", "type": "chatInputNode", "data": {"name": "Start"}})
        nodes.append({"id": "out", "type": "chatOutputNode", "data": {"name": "Finish"}})
        edges.insert(0, {"source": "in", "target": "prep", "sourceHandle": "output", "targetHandle": "input"})
        edges.append({"source": "next", "target": "out", "sourceHandle": "output", "targetHandle": "input"})
    workflow = {"id": "wf1", "config": {"id": "wf1"}, "nodes": nodes, "edges": edges}
    if grouped:
        workflow = copy.deepcopy(workflow)
        for node in workflow["nodes"]:
            if node["id"] in ("prep", "next"):
                node["parentId"] = "g1"
        # Groups are stored first (React Flow needs parents before children).
        workflow["nodes"].insert(0, copy.deepcopy(GROUP))
    return workflow


def test_executable_nodes_drops_only_groups():
    nodes = _workflow(grouped=True)["nodes"]
    assert [n["id"] for n in executable_nodes(nodes)] == ["in", "prep", "next", "out"]


def test_engine_never_sees_group_nodes():
    engine = WorkflowEngine(_workflow(grouped=True))
    assert all(n["type"] != "groupNode" for n in engine.workflow["nodes"])
    assert engine.get_workflow_status()["node_count"] == 4


def test_group_is_not_an_inferred_starting_node():
    # Without a chat input, every node lacking incoming edges is a start node — a group (which
    # never has edges) would otherwise be picked and fail as an unknown node type.
    engine = WorkflowEngine(_workflow(with_input=False, grouped=True))
    assert engine._find_starting_nodes() == ["prep"]


@pytest.mark.asyncio
@pytest.mark.parametrize("with_input", [True, False])
async def test_grouped_workflow_runs_identically(with_input):
    plain = await WorkflowEngine(_workflow(with_input)).execute_from_node(
        input_data={"message": "hi"}, persist=False
    )
    grouped = await WorkflowEngine(_workflow(with_input, grouped=True)).execute_from_node(
        input_data={"message": "hi"}, persist=False
    )
    assert grouped.status == plain.status
    assert grouped.node_outputs == plain.node_outputs
    assert grouped.node_outputs["next"] == "got: prepared hi"
    assert "g1" not in grouped.node_outputs
