"""A run's status reports node failures: "failed" or "partial", never "success".

format_state_as_response used to return "success" for every finished run, so a
failed node only showed in has_failures / failed_nodes and many failures
looked like successes.

The helpers record node runs the way BaseNode.execute does: a node that
succeeds stores its output; a node that raises is marked failed and stores no
output (so the nodes after it never run); a node that fails by returning an
error envelope is marked failed but still passes an output on.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.routes import workflows as workflow_routes
from app.modules.workflow.agents.sub_agents.turn_router import SubAgentTurnRouter
from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes.workflow_executor_node import WorkflowExecutorNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState, failed_nodes_summary, run_failure_message

THREAD = "11111111-1111-1111-1111-111111111111"


def _edge(edge):
    """(source, target) or (source, target, sourceHandle, targetHandle)."""
    source, target, *handles = edge
    source_handle, target_handle = (handles + [None, None])[:2]
    return {"source": source, "target": target, "sourceHandle": source_handle, "targetHandle": target_handle}


def _state(node_ids, edges=(), types=None) -> WorkflowState:
    types = types or {}
    nodes = [
        {"id": node_id, "type": types.get(node_id, "testNode"), "data": {"name": node_id}} for node_id in node_ids
    ]
    workflow = {"nodes": nodes, "edges": [_edge(edge) for edge in edges]}
    state = WorkflowState(workflow=workflow, thread_id=THREAD, initial_values={"message": "hi"})
    state.start_execution()
    return state


def _succeeds(state, node_id, output):
    state.start_node_execution(node_id)
    state.set_node_output(node_id, output)
    state.complete_node_execution(node_id, output, None)


def _raises(state, node_id, error):
    state.start_node_execution(node_id)
    state.complete_node_execution(node_id, None, error)


def _fails_with_output(state, node_id, output, error):
    state.start_node_execution(node_id)
    state.set_node_output(node_id, output)
    state.complete_node_execution(node_id, output, error)


def _response(state) -> dict:
    state.complete_execution()
    return state.format_state_as_response()


CHAT = [("input", "agent"), ("agent", "output")]


def test_a_fully_successful_run_is_success():
    state = _state(["input", "agent", "output"], CHAT)
    _succeeds(state, "input", "hi")
    _succeeds(state, "agent", "hello")
    _succeeds(state, "output", "hello")

    response = _response(state)

    assert response["status"] == "success"
    assert response["has_failures"] is False
    assert response["failed_nodes"] == []


def test_a_single_node_that_raises_is_failed():
    state = _state(["train"])
    _raises(state, "train", "Column 'y' not found")

    response = _response(state)

    assert response["status"] == "failed"
    assert response["failed_nodes"] == [
        {"node_id": "train", "name": "train", "type": "testNode", "error": "Column 'y' not found"}
    ]


def test_an_agent_that_raises_before_chat_output_is_failed():
    # Chat Output never runs: its source has no output.
    state = _state(["input", "agent", "output"], CHAT)
    _succeeds(state, "input", "hi")
    _raises(state, "agent", "LLM provider unavailable")

    response = _response(state)

    assert response["status"] == "failed"
    assert [n["node_id"] for n in response["failed_nodes"]] == ["agent"]


def test_a_failed_middle_node_with_an_answer_is_partial():
    state = _state(["input", "ticket", "output"], [("input", "ticket"), ("ticket", "output")])
    _succeeds(state, "input", "hi")
    _fails_with_output(state, "ticket", {"error": "Zendesk refused"}, "Zendesk refused the ticket")
    _succeeds(state, "output", "Your ticket is being handled")

    response = _response(state)

    assert response["status"] == "partial"
    assert response["output"] == "Your ticket is being handled"
    assert failed_nodes_summary(response) == "ticket: Zendesk refused the ticket"


def test_a_failed_end_node_that_returned_an_error_body_is_failed():
    state = _state(["input", "api"], [("input", "api")])
    _succeeds(state, "input", "hi")
    _fails_with_output(state, "api", {"status": 500, "body": "boom"}, "HTTP 500")

    assert _response(state)["status"] == "failed"


def test_a_side_branch_does_not_hide_an_agent_that_failed_before_chat_output():
    # Chat Input fans out to [Agent -> Chat Output] and [Slack]. The Agent raised,
    # so Chat Output never ran; the Slack branch finishing is not an answer.
    edges = [("input", "agent"), ("agent", "output"), ("input", "slack")]
    state = _state(["input", "agent", "output", "slack"], edges, types={"output": "chatOutputNode"})
    _succeeds(state, "input", "hi")
    _succeeds(state, "slack", {"ok": True})
    _raises(state, "agent", "LLM provider timed out")

    response = _response(state)

    assert response["status"] == "failed"
    assert [n["node_id"] for n in response["failed_nodes"]] == ["agent"]


def test_a_failed_side_branch_with_an_answered_chat_output_is_partial():
    edges = [("input", "agent"), ("agent", "output"), ("input", "slack")]
    state = _state(["input", "agent", "output", "slack"], edges, types={"output": "chatOutputNode"})
    _succeeds(state, "input", "hi")
    _fails_with_output(state, "slack", {"error": "x"}, "Slack refused the message")
    _succeeds(state, "agent", "hello")
    _succeeds(state, "output", "hello")

    assert _response(state)["status"] == "partial"


def test_a_side_branch_finishing_after_chat_output_is_not_the_reply():
    edges = [("input", "agent"), ("agent", "output"), ("input", "slack")]
    state = _state(["input", "agent", "output", "slack"], edges, types={"output": "chatOutputNode"})
    _succeeds(state, "input", "hi")
    _succeeds(state, "agent", "hello")
    _succeeds(state, "output", "hello")
    _succeeds(state, "slack", {"ok": True})

    assert _response(state)["output"] == "hello"


@pytest.mark.parametrize("branch_a_last", [True, False])
def test_parallel_branches_give_the_same_status_whichever_finishes_last(branch_a_last):
    edges = [("input", "a"), ("input", "b")]
    state = _state(["input", "a", "b"], edges)
    _succeeds(state, "input", "hi")
    steps = [
        lambda: _fails_with_output(state, "a", {"error": "x"}, "branch A failed"),
        lambda: _succeeds(state, "b", "branch B answer"),
    ]
    for step in (steps[::-1] if branch_a_last else steps):
        step()

    assert _response(state)["status"] == "partial"


def test_a_tool_sub_flow_that_succeeded_does_not_make_a_failed_agent_partial():
    # Chat Input -> Agent -> Chat Output, with a Tool Builder (sub-flow: step -> last)
    # attached to the Agent. The tool's last node is not an end of the main flow.
    edges = CHAT + [
        ("tool", "agent", "output_tool", "input_tools"),
        ("tool", "step", "starter_processor", None),
        ("step", "last"),
    ]
    state = _state(["input", "agent", "output", "tool", "step", "last"], edges)
    _succeeds(state, "input", "hi")
    _succeeds(state, "step", "looked up")
    _succeeds(state, "last", "tool answer")
    _raises(state, "agent", "LLM provider unavailable")

    assert _response(state)["status"] == "failed"


def test_an_entry_agent_with_a_tool_attached_still_reaches_its_end():
    # Agent (entry, a tool hung on it) -> Chat Output. The tool failed once but
    # the agent recovered and answered, so the run is partial, not failed.
    edges = [("agent", "output"), ("tool", "agent", "output_tool", "input_tools")]
    state = _state(["agent", "output", "tool"], edges)
    _raises(state, "tool", "lookup timed out")
    _succeeds(state, "agent", "Here is what I found")
    _succeeds(state, "output", "Here is what I found")

    assert _response(state)["status"] == "partial"


def test_the_run_record_names_both_the_failed_node_and_what_stopped_the_run():
    state = _state(["input", "ticket", "next"], [("input", "ticket"), ("ticket", "next")])
    _succeeds(state, "input", "hi")
    _fails_with_output(state, "ticket", {"error": "x"}, "Zendesk refused")
    state.fail_execution("Node next failed: unknown node type")
    response = state.format_state_as_response()

    assert run_failure_message(state, response) == "ticket: Zendesk refused; Node next failed: unknown node type"


def test_a_loop_body_is_not_an_end_of_the_main_flow():
    edges = [
        ("input", "loop"),
        ("loop", "body", "output_loop", None),
        ("body", "loop", None, "input_loop"),
        ("loop", "output", "output_done", None),
    ]
    state = _state(["input", "loop", "body", "output"], edges)
    _succeeds(state, "input", "hi")
    _succeeds(state, "body", "item done")
    _raises(state, "loop", "loop failed")

    assert _response(state)["status"] == "failed"


def test_an_error_the_engine_swallowed_fails_the_run():
    # A node that could not even be built: recorded by the engine, not by a node.
    # It was the only way on, so the run never reached an end.
    state = _state(["input", "ghost"], [("input", "ghost")])
    _succeeds(state, "input", "hi")
    state.fail_execution("Node ghost failed: unknown node type")

    response = _response(state)

    assert response["status"] == "failed"
    assert run_failure_message(state, response) == "Node ghost failed: unknown node type"


def test_a_stopped_parallel_branch_with_an_answered_end_is_partial():
    # Chat Input fans out to [Agent -> Chat Output] and [ghost]. The ghost branch
    # stopped outside any node, but Chat Output still answered.
    edges = [("input", "agent"), ("agent", "output"), ("input", "ghost")]
    state = _state(["input", "agent", "output", "ghost"], edges)
    _succeeds(state, "input", "hi")
    state.fail_execution("Node ghost failed: unknown node type")
    _succeeds(state, "agent", "hello")
    _succeeds(state, "output", "hello")

    assert _response(state)["status"] == "partial"


@pytest.mark.asyncio
async def test_a_node_the_engine_could_not_build_fails_the_run():
    # The second node's type is not registered: building it raises inside the
    # engine's parallel branch, outside any node, and used to be only logged.
    workflow = {
        "id": "wf-ghost",
        "nodes": [
            {"id": "input", "type": "chatInputNode", "data": {"name": "Chat Input"}},
            {"id": "ghost", "type": "noSuchNodeType", "data": {"name": "Ghost"}},
        ],
        "edges": [{"source": "input", "target": "ghost"}],
    }
    state = await WorkflowEngine(workflow).execute_from_node(input_data={"message": "hi"}, thread_id=THREAD)
    response = state.format_state_as_response()

    assert response["status"] == "failed"
    assert "Node ghost failed" in run_failure_message(state, response)


def test_the_run_record_names_the_failed_nodes():
    state = _state(["train"])
    _raises(state, "train", "Column 'y' not found")
    response = _response(state)

    assert run_failure_message(state, response) == "train: Column 'y' not found"


def test_a_successful_run_has_no_failure_message():
    state = _state(["input"])
    _succeeds(state, "input", "hi")
    response = _response(state)

    assert run_failure_message(state, response) is None


def test_a_run_the_engine_stopped_is_failed():
    state = _state(["input"])
    _succeeds(state, "input", "hi")
    state.fail_execution("Node x failed: unexpected error")

    assert state.format_state_as_response()["status"] == "failed"


def test_a_node_that_failed_then_succeeded_on_a_rerun_is_success():
    state = _state(["loop_body"])
    _raises(state, "loop_body", "first pass failed")
    _succeeds(state, "loop_body", "second pass ok")

    response = _response(state)

    assert response["status"] == "success"
    assert response["failed_nodes"] == []


def test_a_paused_run_stays_awaiting_input():
    state = _state(["form"])
    _succeeds(state, "form", {"status": "awaiting_input", "form_schema": {}})
    state.output = {"status": "awaiting_input", "form_schema": {}}

    assert _response(state)["status"] == "awaiting_input"


@pytest.mark.asyncio
async def test_test_node_on_a_node_that_fails_returns_failed():
    # A Train Data Source whose file doesn't exist fails inside the node. (Train
    # Model can't be used here: its node tests run as background jobs.)
    response = await workflow_routes.test_individual_node(SimpleNamespace(headers={}), {
        "node_type": "trainDataSourceNode",
        "node_config": {"name": "d", "sourceType": "csv", "fileUrl": "missing.csv"},
        "input_data": {},
    })

    assert response["status"] == "failed"
    assert response["has_failures"] is True
    assert response["failed_nodes"][0]["type"] == "trainDataSourceNode"


@pytest.mark.parametrize(
    "status, has_failures, text, expected",
    [
        # The sub-agent replied although a tool failed: the child run uses the
        # parent's graph, so its own status is "failed", but the turn answered
        ("failed", True, "Is a layover okay?", "partial"),
        ("failed", False, "Is a layover okay?", "partial"),
        ("partial", True, "Is a layover okay?", "partial"),
        ("awaiting_input", True, "Is a layover okay?", "partial"),
        ("awaiting_input", False, "Is a layover okay?", "success"),
        ("success", False, "Is a layover okay?", "success"),
        # No reply at all: the turn failed
        ("failed", True, "", "failed"),
        ("failed", False, "", "failed"),
    ],
)
def test_a_sub_agent_message_keeps_a_failure(status, has_failures, text, expected):
    router = SubAgentTurnRouter(WorkflowEngine({"id": "wf1", "nodes": [], "edges": []}), owner_id="agentA")
    response = {"status": status, "has_failures": has_failures, "output": {}}

    assert router._message_only(response, text)["status"] == expected


def _executor_with_child(child_state):
    workflow = MagicMock(id="22222222-2222-2222-2222-222222222222", nodes=[], edges=[])
    workflow.name = "Child flow"
    service = MagicMock(get_by_id=AsyncMock(return_value=workflow))
    injector = MagicMock(get=MagicMock(return_value=service))

    async def execute(self, **kwargs):
        return child_state

    parent = WorkflowState(workflow={"nodes": [], "edges": []}, thread_id=THREAD, initial_values={})
    node = WorkflowExecutorNode("exec-1", {"type": "workflowExecutorNode", "data": {}}, parent)
    return node, patch("app.dependencies.injector.injector", injector), patch.object(WorkflowEngine, "execute_from_node", execute)


@pytest.mark.asyncio
async def test_a_failed_sub_workflow_fails_its_executor_node():
    child = _state(["step"])
    _raises(child, "step", "API unreachable")
    child.complete_execution()
    node, injector, engine = _executor_with_child(child)

    with injector, engine:
        result = await node.process({"workflowId": "22222222-2222-2222-2222-222222222222", "inputParameters": {}})

    failure = is_node_failure(result)
    assert failure is not None
    assert "Child flow failed - step: API unreachable" in failure["error"]
    # Only the status is passed on, not the sub-workflow's internals
    assert failure["output"] == {
        "status": "failed",
        "workflow_id": "22222222-2222-2222-2222-222222222222",
        "workflow_name": "Child flow",
    }


@pytest.mark.asyncio
async def test_a_partial_sub_workflow_passes_its_answer_on_and_makes_the_parent_partial():
    child = _state(["ticket", "answer"], [("ticket", "answer")])
    _fails_with_output(child, "ticket", {"error": "x"}, "Zendesk refused")
    _succeeds(child, "answer", "We'll get back to you")
    child.complete_execution()
    node, injector, engine = _executor_with_child(child)
    parent = node.get_state()
    parent.workflow = {"nodes": [{"id": "exec-1", "type": "workflowExecutorNode", "data": {}}], "edges": []}
    parent.start_execution()
    parent.start_node_execution("exec-1")

    with injector, engine:
        result = await node.process({"workflowId": "22222222-2222-2222-2222-222222222222", "inputParameters": {}})
    parent.set_node_output("exec-1", result)
    parent.complete_node_execution("exec-1", result, None)

    # The node answered, so an Agent using it as a tool gets the answer, not an error
    assert is_node_failure(result) is None
    assert result["status"] == "partial"
    assert result["result"]["output"] == "We'll get back to you"
    # The parent's last node answered, so the parent is partial (not failed) and
    # still lists what went wrong inside the sub-workflow
    response = _response(parent)
    assert response["status"] == "partial"
    assert "Child flow partial - ticket: Zendesk refused" in response["failed_nodes"][0]["error"]


@pytest.mark.asyncio
async def test_a_successful_sub_workflow_still_succeeds():
    child = _state(["step"])
    _succeeds(child, "step", "done")
    child.complete_execution()
    node, injector, engine = _executor_with_child(child)

    with injector, engine:
        result = await node.process({"workflowId": "22222222-2222-2222-2222-222222222222", "inputParameters": {}})

    assert is_node_failure(result) is None
    assert result["status"] == "success"
