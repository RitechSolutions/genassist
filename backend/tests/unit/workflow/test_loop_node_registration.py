"""Registration and save-time wiring tests for LoopNode ("Loop")."""

import pytest

from app.api.v1.routes.workflows import SUPPORTED_NODE_TYPES
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.conditions import OPERATORS
from app.modules.workflow.engine.loops import LoopTopologyError, loop_body, validate_loop_topology
from app.modules.workflow.engine.nodes.loop_node import COLLECT_MODES, MODES, LoopNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.schemas.dynamic_form_schemas.nodes import (
    NODE_DIALOG_SCHEMAS,
    NODE_HANDLERS_SCHEMAS,
    NODE_TYPE_LABELS,
)
from app.services.workflow import WorkflowService

_NODE_TYPE = "loopNode"


def test_node_type_resolves_to_class_in_engine_registry():
    WorkflowEngine._initialize_node_registry()
    assert WorkflowEngine._node_registry.get(_NODE_TYPE) is LoopNode


def test_node_type_is_supported_by_the_api():
    assert _NODE_TYPE in SUPPORTED_NODE_TYPES


def test_dialog_schema_fields_modes_and_operators():
    schema = {field.name: field for field in NODE_DIALOG_SCHEMAS[_NODE_TYPE]}
    assert {
        "name", "mode", "items", "batchSize", "maxIterations", "stopField", "stopOperator", "stopValue",
        "stopCaseSensitive", "onError", "delaySeconds", "delayBackoff", "timeLimitSeconds", "collect",
    } <= set(schema)
    assert [o["value"] for o in schema["collect"].options] == list(COLLECT_MODES)
    assert [o["value"] for o in schema["mode"].options] == list(MODES)
    assert [o["value"] for o in schema["stopOperator"].options] == list(OPERATORS)
    assert [o["value"] for o in schema["onError"].options] == ["stop", "continue"]


def test_handlers_declare_the_body_and_done_outputs_and_the_loop_back_input():
    assert [(h["id"], h["type"]) for h in NODE_HANDLERS_SCHEMAS[_NODE_TYPE]] == [
        ("input", "target"),
        ("input_loop", "target"),
        ("output_loop", "source"),
        ("output_done", "source"),
    ]


def test_node_type_label_registered():
    assert NODE_TYPE_LABELS.get(_NODE_TYPE) == "Loop"


def test_node_reported_as_not_needing_db_access():
    engine = WorkflowEngine.__new__(WorkflowEngine)
    assert engine._node_needs_db_access(_NODE_TYPE) is False


# ---- save-time wiring -------------------------------------------------------


def _node(node_id, node_type="templateNode"):
    return {"id": node_id, "type": node_type, "data": {"name": node_id.title()}}


def _edge(source, target, source_handle="output", target_handle="input"):
    return {"source": source, "target": target, "sourceHandle": source_handle, "targetHandle": target_handle}


def _looped(*extra_edges, body_type="templateNode"):
    nodes = [_node("start"), _node("loop", "loopNode"), _node("a", body_type), _node("b"), _node("after"), _node("other")]
    edges = [
        _edge("start", "loop"),
        _edge("loop", "a", "output_loop"),
        _edge("a", "b"),
        _edge("b", "loop", target_handle="input_loop"),
        _edge("loop", "after", "output_done"),
        *extra_edges,
    ]
    return nodes, edges


def test_a_correctly_wired_loop_is_accepted():
    validate_loop_topology(*_looped())


def test_workflows_without_a_loop_are_not_checked():
    validate_loop_topology([_node("a"), _node("b")], [_edge("a", "b"), _edge("b", "a")])


def test_an_unconnected_draft_loop_saves():
    validate_loop_topology([_node("loop", "loopNode")], [])


def test_the_body_is_what_the_loop_output_reaches_and_ends_at_the_back_edge():
    nodes, edges = _looped()
    source_edges = {}
    for edge in edges:
        source_edges.setdefault(edge["source"], []).append(edge)
    assert loop_body("loop", source_edges) == {"a", "b"}


def test_loop_back_from_outside_the_body_is_rejected():
    with pytest.raises(LoopTopologyError, match="not part of this loop's body"):
        validate_loop_topology(*_looped(_edge("other", "loop", target_handle="input_loop")))


def test_human_in_the_loop_inside_a_body_is_rejected():
    with pytest.raises(LoopTopologyError, match="not supported inside a loop"):
        validate_loop_topology(*_looped(body_type="humanInTheLoopNode"))


def _agent_in_body(*attached_nodes, edges=()):
    """The loop of ``_looped`` with an agent as body node ``a`` and things attached to it."""
    nodes, base_edges = _looped(body_type="agentNode")
    return [*nodes, *attached_nodes], [*base_edges, *edges]


def _sub_agent(node_id, mode):
    return {"id": node_id, "type": "subAgentNode", "data": {"name": node_id.title(), "mode": mode}}


@pytest.mark.parametrize("mode", ["task", "chat"])
def test_an_interactive_sub_agent_of_a_body_agent_is_rejected(mode):
    nodes, edges = _agent_in_body(
        _sub_agent("helper", mode), edges=[_edge("helper", "a", "output_sub_agent", "input_sub_agents")]
    )
    with pytest.raises(LoopTopologyError, match="'Helper' pauses the workflow .* and 'A' in the loop's body uses it"):
        validate_loop_topology(nodes, edges)


def test_an_interactive_sub_agent_below_a_single_turn_one_is_rejected():
    nodes, edges = _agent_in_body(
        _sub_agent("helper", "single_turn"),
        _sub_agent("deep", "chat"),
        edges=[
            _edge("helper", "a", "output_sub_agent", "input_sub_agents"),
            _edge("deep", "helper", "output_sub_agent", "input_sub_agents"),
        ],
    )
    with pytest.raises(LoopTopologyError, match="'Deep' pauses"):
        validate_loop_topology(nodes, edges)


def test_a_tool_whose_sub_flow_pauses_is_rejected_on_a_body_agent():
    nodes, edges = _agent_in_body(
        _node("tool", "toolBuilderNode"),
        _node("fetch"),
        _node("approve", "humanInTheLoopNode"),
        edges=[
            _edge("tool", "a", "output_tool", "input_tools"),
            _edge("tool", "fetch", "starter_processor"),
            _edge("fetch", "approve"),
        ],
    )
    with pytest.raises(LoopTopologyError, match="'Approve' pauses the workflow .* 'A' in the loop's body uses it"):
        validate_loop_topology(nodes, edges)


def test_agents_with_tools_and_single_turn_sub_agents_are_allowed_in_a_body():
    nodes, edges = _agent_in_body(
        _sub_agent("helper", "single_turn"),
        _sub_agent("unset", None),
        _node("tool", "toolBuilderNode"),
        _node("fetch"),
        edges=[
            _edge("helper", "a", "output_sub_agent", "input_sub_agents"),
            _edge("unset", "a", "output_sub_agent", "input_sub_agents"),
            _edge("tool", "a", "output_tool", "input_tools"),
            _edge("tool", "fetch", "starter_processor"),
        ],
    )
    validate_loop_topology(nodes, edges)


def test_what_pauses_outside_the_loop_is_not_blamed_on_it():
    # The tool is shared with an agent after the loop, which is followed by a Human in the Loop
    # node and has an interactive sub-agent of its own.
    nodes, edges = _agent_in_body(
        _node("tool", "toolBuilderNode"),
        _node("fetch"),
        _node("outside", "agentNode"),
        _node("approve", "humanInTheLoopNode"),
        _sub_agent("helper", "chat"),
        edges=[
            _edge("tool", "a", "output_tool", "input_tools"),
            _edge("tool", "outside", "output_tool", "input_tools"),
            _edge("tool", "fetch", "starter_processor"),
            _edge("after", "outside"),
            _edge("outside", "approve"),
            _edge("helper", "outside", "output_sub_agent", "input_sub_agents"),
        ],
    )
    validate_loop_topology(nodes, edges)


def test_a_body_node_that_also_feeds_the_done_branch_is_rejected():
    with pytest.raises(LoopTopologyError, match="from Done only"):
        validate_loop_topology(*_looped(_edge("b", "after")))


def test_the_service_reports_bad_wiring_with_the_loop_error_key():
    nodes, edges = _looped(_edge("b", "after"))
    with pytest.raises(AppException) as exc:
        WorkflowService._validate_loops({"nodes": nodes, "edges": edges})
    assert exc.value.status_code == 400
    assert exc.value.error_key == ErrorKey.LOOP_INVALID_TOPOLOGY
