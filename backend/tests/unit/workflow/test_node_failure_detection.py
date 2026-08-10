"""Tests for the node-failure detection contract.

Covers:
- node_result.node_failure / is_node_failure (canonical envelope + conservative
  legacy shapes, and the non-failure cases it must NOT flag).
- BaseNode.execute(): a node that fails WITHOUT raising (error envelope / HTTP-500
  body) is recorded as "failed" while the workflow keeps its (partial) output; a
  node that raises is recorded as failed and returns a detectable failure envelope;
  a normal node is still "success".
- WorkflowState._collect_failed_nodes(): reports failed nodes, latest run only.
- BaseTool.invoke(): a failing tool yields an explicit error observation instead of
  a bare None/error dict, so an agent cannot silently treat it as success.
"""

import pytest

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.engine.node_result import (
    NODE_FAILURE_MARKER,
    is_node_failure,
    node_failure,
)
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.modules.workflow.agents.base_tool import BaseTool


# --------------------------------------------------------------------------- #
# node_result contract
# --------------------------------------------------------------------------- #

def test_canonical_envelope_detected_and_carries_output():
    env = node_failure("boom", code=502, output={"message": "sorry"})
    assert env[NODE_FAILURE_MARKER] is True
    info = is_node_failure(env)
    assert info["error"] == "boom"
    assert info["code"] == 502
    assert info["output"] == {"message": "sorry"}


@pytest.mark.parametrize("result,expected_error", [
    ({"status": 500, "data": {"error": "e"}}, "e"),
    ({"status": 404, "data": {"error": "not found"}}, "not found"),
    ({"status": "error", "output": "oops"}, "oops"),
    ({"success": False, "error": "q"}, "q"),
])
def test_legacy_failure_shapes_detected(result, expected_error):
    info = is_node_failure(result)
    assert info is not None
    assert info["error"] == expected_error
    # Legacy shapes flow their whole dict downstream unchanged.
    assert info["output"] == result


@pytest.mark.parametrize("result", [
    {"status": 200, "data": {}},          # HTTP OK
    {"status": "awaiting_input"},          # human-in-the-loop pause
    {"next_nodes": ["a"]},                 # router output
    {"status": True},                      # bool guard (True is an int)
    {"error": "bare"},                     # conservative: bare error not auto-flagged
    None,
    "a string",
    42,
])
def test_non_failures_not_flagged(result):
    assert is_node_failure(result) is None


# --------------------------------------------------------------------------- #
# BaseNode.execute() integration
# --------------------------------------------------------------------------- #

class _FakeNode(BaseNode):
    """Minimal node whose process() returns/raises whatever the test wants."""

    def __init__(self, node_id, state, behaviour):
        super().__init__(node_id, {"id": node_id, "type": "fakeNode", "data": {"name": "Fake"}}, state)
        self._behaviour = behaviour

    async def process(self, config):
        return self._behaviour()


def _bare_state(node_id="n1"):
    """A WorkflowState with only the attributes execute() touches (no Redis/memory)."""
    st = WorkflowState.__new__(WorkflowState)
    st.workflow = {"nodes": [{"id": node_id, "type": "fakeNode", "data": {"name": "Fake"}}]}
    st.workflow_id = "wf"
    st.initial_values = {}
    st.node_execution_status = {}
    st.node_inputs = {}
    st.node_outputs = {}
    st.execution_path = []
    st.execution_history = []
    st.errors = []
    st.llm_usage = []
    st.target_edges = {}
    st.source_edges = {}
    return st


@pytest.mark.asyncio
async def test_execute_records_canonical_failure_but_keeps_flow_output():
    st = _bare_state()
    node = _FakeNode("n1", st, lambda: node_failure("ticket not created", code=502, output={"message": "sorry"}))

    returned = await node.execute()

    # Recorded as failed with the error message.
    assert st.node_execution_status["n1"]["status"] == "failed"
    assert st.node_execution_status["n1"]["error"] == "ticket not created"
    # Downstream/user still sees the flow-compatible (partial) output, not the envelope.
    assert st.get_node_output("n1") == {"message": "sorry"}
    assert NODE_FAILURE_MARKER not in st.get_node_output("n1")
    # The raw envelope is returned so a tool caller can also detect the failure.
    assert is_node_failure(returned) is not None


@pytest.mark.asyncio
async def test_execute_records_legacy_http_failure():
    st = _bare_state()
    node = _FakeNode("n1", st, lambda: {"status": 500, "data": {"error": "upstream 500"}})

    await node.execute()

    assert st.node_execution_status["n1"]["status"] == "failed"
    assert "upstream 500" in st.node_execution_status["n1"]["error"]
    # Legacy dict flows downstream unchanged.
    assert st.get_node_output("n1") == {"status": 500, "data": {"error": "upstream 500"}}


@pytest.mark.asyncio
async def test_execute_on_raise_marks_failed_and_returns_detectable_envelope():
    st = _bare_state()

    def _boom():
        raise RuntimeError("kaboom")

    node = _FakeNode("n1", st, _boom)
    returned = await node.execute()

    assert st.node_execution_status["n1"]["status"] == "failed"
    assert "kaboom" in st.node_execution_status["n1"]["error"]
    # A caller using this node as a tool must be able to detect the failure.
    assert is_node_failure(returned) is not None


@pytest.mark.asyncio
async def test_execute_normal_output_is_success():
    st = _bare_state()
    node = _FakeNode("n1", st, lambda: {"message": "all good"})

    returned = await node.execute()

    assert st.node_execution_status["n1"]["status"] == "success"
    assert st.node_execution_status["n1"]["error"] is None
    assert st.get_node_output("n1") == {"message": "all good"}
    assert returned == {"message": "all good"}


# --------------------------------------------------------------------------- #
# WorkflowState._collect_failed_nodes()
# --------------------------------------------------------------------------- #

def test_collect_failed_nodes_reports_only_failed():
    st = WorkflowState.__new__(WorkflowState)
    st.node_execution_status = {
        "a": {"status": "success", "name": "A", "type": "t", "error": None},
        "b": {"status": "failed", "name": "B", "type": "zendeskTicketNode", "error": "no ticket"},
    }
    failed = st._collect_failed_nodes()
    assert [f["node_id"] for f in failed] == ["b"]
    assert failed[0]["error"] == "no ticket"
    assert failed[0]["type"] == "zendeskTicketNode"


def test_collect_failed_nodes_ignores_archived_earlier_runs():
    # Node "b" failed on its first run ("b_0") but the latest run ("b") succeeded.
    st = WorkflowState.__new__(WorkflowState)
    st.node_execution_status = {
        "b_0": {"status": "failed", "name": "B", "type": "t", "error": "first try"},
        "b": {"status": "success", "name": "B", "type": "t", "error": None},
    }
    assert st._collect_failed_nodes() == []


# --------------------------------------------------------------------------- #
# BaseTool.invoke() agent honesty
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_tool_invoke_surfaces_failure_as_error_observation():
    async def failing(_inp):
        return node_failure("Zendesk ticket was not created", code=502)

    tool = BaseTool(node_id="z", name="Create Zendesk Ticket", description="d", parameters={}, function=failing)
    out = await tool.invoke(subject="x", description="y")

    assert isinstance(out, str)
    assert "did not complete successfully" in out
    assert "Zendesk ticket was not created" in out


@pytest.mark.asyncio
async def test_tool_invoke_passes_success_through_unchanged():
    async def ok(_inp):
        return {"status": 200, "data": {"id": 1}}

    tool = BaseTool(node_id="z", name="ok", description="d", parameters={}, function=ok)
    assert await tool.invoke() == {"status": 200, "data": {"id": 1}}
