"""Tests for FilterNode: the gate decision, pass-through of its input, stopping
the branch (with an optional chat reply), and real engine runs."""

import logging
from types import SimpleNamespace

import pytest

from app.modules.workflow.engine.nodes.filter_node import FilterNode

UPSTREAM = {"status": "active", "score": 0.92, "email": "a@b.co"}


def _make_node(upstream=UPSTREAM):
    node = FilterNode("f", {"type": "filterNode", "data": {"name": "Filter"}}, SimpleNamespace())
    node.get_input_from_source = lambda: upstream
    return node


@pytest.mark.asyncio
async def test_passing_condition_forwards_the_input_unchanged():
    result = await _make_node().process({"field": "active", "operator": "equal", "value": "Active"})
    assert result == UPSTREAM


@pytest.mark.asyncio
async def test_failing_condition_stops_the_branch():
    result = await _make_node().process({"field": "blocked", "operator": "equal", "value": "active"})
    assert result["next_nodes"] == []
    assert result["passed"] is False
    assert result["message"] == ""
    assert result["field"] == "blocked" and result["operator"] == "equal" and result["value"] == "active"


@pytest.mark.asyncio
async def test_stop_message_is_returned_as_the_reply():
    result = await _make_node().process(
        {"field": "0.4", "operator": "greater_than", "value": "0.8", "stopMessage": "  Not confident enough.  "}
    )
    assert result["message"] == "Not confident enough."
    assert result["next_nodes"] == []


@pytest.mark.asyncio
async def test_threshold_and_presence_checks():
    node = _make_node()
    assert await node.process({"field": "0.92", "operator": "greater_than_or_equal", "value": "0.9"}) == UPSTREAM
    assert await node.process({"field": "a@b.co", "operator": "is_not_empty"}) == UPSTREAM
    stopped = await node.process({"field": "null", "operator": "is_not_empty"})
    assert stopped["passed"] is False


@pytest.mark.asyncio
async def test_is_empty_passes_on_a_missing_field():
    assert await _make_node().process({"field": "", "operator": "is_empty"}) == UPSTREAM


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config",
    [
        {"field": "", "operator": "equal", "value": "x"},  # nothing to check
        {"field": "abc", "operator": "fuzzy", "value": "abc"},  # unknown operator
        {"field": "abc", "operator": "regex", "value": "(unclosed"},  # broken regex
        {"field": "abc", "operator": "equal"},  # value missing
    ],
)
async def test_broken_conditions_fail_closed(config, caplog):
    with caplog.at_level(logging.WARNING):
        result = await _make_node().process(config)
    assert result["passed"] is False and result["next_nodes"] == []


@pytest.mark.asyncio
async def test_routing_keys_from_the_input_do_not_leak_downstream():
    upstream = {"route": "case_1", "label": "Billing", "next_nodes": ["somewhere_else"]}
    result = await _make_node(upstream).process({"field": "x", "operator": "equal", "value": "x"})
    assert "next_nodes" not in result
    assert result == {"route": "case_1", "label": "Billing"}


@pytest.mark.asyncio
async def test_non_dict_input_is_forwarded_as_is():
    assert await _make_node("plain text").process({"field": "x", "operator": "equal", "value": "x"}) == "plain text"


@pytest.mark.asyncio
async def test_without_input_a_pass_reports_the_decision():
    result = await _make_node(None).process({"field": "x", "operator": "equal", "value": "x"})
    assert result == {"passed": True, "field": "x", "operator": "equal", "value": "x"}


# ---- engine ----------------------------------------------------------------


def _workflow(filter_data, before=None):
    before = before or {"id": "prep", "type": "templateNode", "data": {"name": "Prep", "template": "prepared {{session.message}}"}}
    return {
        "id": "wf1",
        "config": {"id": "wf1"},
        "nodes": [
            {"id": "in", "type": "chatInputNode", "data": {"name": "Start"}},
            before,
            {"id": "f", "type": "filterNode", "data": {"name": "Filter", **filter_data}},
            {"id": "next", "type": "templateNode", "data": {"name": "Next", "template": "got: {{source}}"}},
            {"id": "out", "type": "chatOutputNode", "data": {"name": "Finish"}},
        ],
        "edges": [
            {"source": "in", "target": before["id"], "sourceHandle": "output", "targetHandle": "input"},
            {"source": before["id"], "target": "f", "sourceHandle": "output", "targetHandle": "input"},
            {"source": "f", "target": "next", "sourceHandle": "output", "targetHandle": "input"},
            {"source": "next", "target": "out", "sourceHandle": "output", "targetHandle": "input"},
        ],
    }


async def _run(workflow, message):
    from app.modules.workflow.engine.workflow_engine import WorkflowEngine

    return await WorkflowEngine(workflow).execute_from_node(input_data={"message": message}, persist=False)


@pytest.mark.asyncio
async def test_engine_continues_and_the_next_node_reads_the_filters_input():
    state = await _run(_workflow({"field": "{{session.message}}", "operator": "equal", "value": "active"}), "Active")
    assert state.node_outputs["f"] == state.node_outputs["prep"] == "prepared Active"
    assert state.node_outputs["next"] == "got: prepared Active"
    assert "out" in state.node_outputs


@pytest.mark.asyncio
async def test_engine_stops_the_branch_and_replies_with_the_stop_message():
    workflow = _workflow(
        {"field": "{{session.message}}", "operator": "equal", "value": "active", "stopMessage": "Only active accounts."}
    )
    state = await _run(workflow, "blocked")
    assert "next" not in state.node_outputs and "out" not in state.node_outputs
    response = state.format_state_as_response()
    assert response["output"]["message"] == "Only active accounts."


@pytest.mark.asyncio
async def test_engine_filter_after_a_switch_is_not_steered_by_the_switch_route():
    switch = {
        "id": "prep",
        "type": "switchNode",
        "data": {"name": "Switch", "switchValue": "{{session.message}}", "cases": [{"id": "case_1", "label": "A", "value": "a"}]},
    }
    workflow = _workflow({"field": "go", "operator": "equal", "value": "go"}, before=switch)
    workflow["edges"][1]["sourceHandle"] = "output_case_1"
    state = await _run(workflow, "a")
    assert "next_nodes" not in state.node_outputs["f"]
    assert "next" in state.node_outputs and "out" in state.node_outputs
