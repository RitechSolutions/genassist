"""Topology validation and semantic fingerprint for sub-agent wiring"""

import pytest

from app.modules.workflow.agents.sub_agents.graph import (
    SubAgentGraph,
    SubAgentTopologyError,
    fingerprint,
    validate_sub_agent_topology,
)


def _agent(node_id, name="Agent"):
    return {"id": node_id, "type": "agentNode", "data": {"name": name}}


def _sub(node_id, name, mode="single_turn"):
    return {"id": node_id, "type": "subAgentNode", "data": {"name": name, "mode": mode}}


def _deleg(child, parent):
    return {
        "source": child,
        "target": parent,
        "sourceHandle": "output_sub_agent",
        "targetHandle": "input_sub_agents",
    }


def _tools_edge(source, target):
    return {"source": source, "target": target, "sourceHandle": "output_tool", "targetHandle": "input_tools"}


def _starter_edge(tool_builder, target):
    return {"source": tool_builder, "target": target, "sourceHandle": "starter_processor", "targetHandle": "input"}


def _validate(nodes, edges):
    SubAgentGraph(nodes, edges).validate()


def test_no_delegations_is_noop():
    validate_sub_agent_topology([_agent("p")], [])


def test_valid_single_child_passes():
    nodes = [_agent("p"), _sub("c", "Helper")]
    _validate(nodes, [_deleg("c", "p")])


def test_source_must_be_sub_agent():
    nodes = [_agent("p"), _agent("c")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c", "p")])
    assert any("not a subAgentNode" in v for v in exc.value.violations)


def test_target_must_be_agent_or_sub_agent():
    nodes = [{"id": "p", "type": "routerNode", "data": {}}, _sub("c", "Helper")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c", "p")])
    assert any("must attach to an agent" in v for v in exc.value.violations)


def test_one_parent_per_child():
    nodes = [_agent("p1"), _agent("p2"), _sub("c", "Helper")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c", "p1"), _deleg("c", "p2")])
    assert any("more than one parent" in v for v in exc.value.violations)


def test_self_link_rejected():
    nodes = [_sub("c", "Helper")]
    with pytest.raises(SubAgentTopologyError):
        _validate(nodes, [_deleg("c", "c")])


def test_cycle_rejected():
    nodes = [_sub("a", "A"), _sub("b", "B")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("b", "a"), _deleg("a", "b")])
    assert any("cycle" in v for v in exc.value.violations)


def test_depth_four_rejected():
    nodes = [_agent("p"), _sub("c1", "C1"), _sub("c2", "C2"), _sub("c3", "C3"), _sub("c4", "C4")]
    edges = [_deleg("c1", "p"), _deleg("c2", "c1"), _deleg("c3", "c2"), _deleg("c4", "c3")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, edges)
    assert any("max delegation depth" in v for v in exc.value.violations)


def test_task_child_must_be_leaf():
    nodes = [_agent("p"), _sub("c1", "C1", mode="task"), _sub("c2", "C2")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c1", "p"), _deleg("c2", "c1")])
    assert any("cannot have its own sub-agents" in v for v in exc.value.violations)


def test_single_turn_subtree_must_stay_single_turn():
    nodes = [_agent("p"), _sub("c1", "C1", mode="single_turn"), _sub("c2", "C2", mode="chat")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c1", "p"), _deleg("c2", "c1")])
    assert any("cannot contain a persistent" in v for v in exc.value.violations)


def test_sibling_name_collision_after_snake_case():
    nodes = [_agent("p"), _sub("c1", "My Child"), _sub("c2", "my_child")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c1", "p"), _deleg("c2", "p")])
    assert any("duplicate sub-agent name" in v for v in exc.value.violations)


def test_reserved_name_rejected():
    nodes = [_agent("p"), _sub("c", "finish_task")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c", "p")])
    assert any("reserved" in v for v in exc.value.violations)


def test_hitl_in_child_tool_subflow_rejected():
    nodes = [
        _agent("p"),
        _sub("c", "Helper"),
        {"id": "tb", "type": "toolBuilderNode", "data": {"name": "T"}},
        {"id": "hitl", "type": "humanInTheLoopNode", "data": {}},
    ]
    edges = [_deleg("c", "p"), _tools_edge("tb", "c"), _starter_edge("tb", "hitl")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, edges)
    assert any("Human-in-the-Loop" in v for v in exc.value.violations)


def test_persistent_child_under_sub_agent_parent_rejected():
    nodes = [_agent("p"), _sub("c1", "C1", mode="chat"), _sub("c2", "C2", mode="task")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c1", "p"), _deleg("c2", "c1")])
    assert any("must attach to a top-level agent" in v for v in exc.value.violations)


def test_task_child_under_tool_subflow_parent_rejected():
    nodes = [
        {"id": "tb", "type": "toolBuilderNode", "data": {"name": "T"}},
        _agent("p"),
        _sub("c", "Helper", mode="chat"),
    ]
    edges = [_starter_edge("tb", "p"), _deleg("c", "p")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, edges)
    assert any("under a tool sub-flow parent" in v for v in exc.value.violations)


def test_all_violations_reported_together():
    nodes = [_agent("p"), _agent("c")]
    with pytest.raises(SubAgentTopologyError) as exc:
        _validate(nodes, [_deleg("c", "p")])
    assert len(exc.value.violations) >= 1


def test_fingerprint_stable_under_ui_only_changes():
    nodes_a = [
        {"id": "p", "type": "agentNode", "data": {"name": "A", "executionState": "idle"}},
        {"id": "c", "type": "subAgentNode", "data": {"name": "H", "mode": "task"}},
    ]
    edges = [_deleg("c", "p")]
    nodes_b = [
        {
            "id": "c",
            "type": "subAgentNode",
            "data": {"name": "H", "mode": "task", "executionState": "running"},
            "position": {"x": 10, "y": 20},
            "selected": True,
            "width": 200,
            "dragging": True,
        },
        {"id": "p", "type": "agentNode", "data": {"name": "A", "executionState": "done"}, "position": {"x": 1, "y": 2}},
    ]
    assert fingerprint(nodes_a, edges) == fingerprint(nodes_b, edges)


def test_fingerprint_changes_on_semantic_change():
    nodes = [_agent("p"), _sub("c", "H", mode="task")]
    edges = [_deleg("c", "p")]
    base = fingerprint(nodes, edges)
    changed_mode = [_agent("p"), _sub("c", "H", mode="chat")]
    assert fingerprint(changed_mode, edges) != base
    assert fingerprint(nodes, []) != base
