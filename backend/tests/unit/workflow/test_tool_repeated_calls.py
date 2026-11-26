"""A tool called more than once in one run works on each call's own arguments.

Runs the real agent tool, Tool Builder, workflow engine, template and set-state nodes.
Stand-in only for the memory that keeps saved values between messages.
"""

from unittest.mock import patch

import pytest

from app.modules.workflow.agents.memory import InMemoryConversationMemory
from app.modules.workflow.engine.nodes.set_state_node import SetStateNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState

THREAD_ID = "acme-thread-1"
QUERIES = ["change delivery address", "cancel an order", "track a parcel"]
SESSION_AT_START = {"message": "Hi", "mode": "standard"}


def _node(node_id: str, node_type: str, **data) -> dict:
    return {"id": node_id, "type": node_type, "data": data}


def _edge(source: str, target: str, source_handle: str = "output", target_handle: str = "input") -> dict:
    return {"source": source, "target": target, "sourceHandle": source_handle, "targetHandle": target_handle}


def _tool(node_id: str, parameter: str, forward_key: str) -> dict:
    """A Tool Builder with one text parameter, forwarded to its steps under the given key."""
    return _node(
        node_id,
        "toolBuilderNode",
        name=node_id,
        description=f"The {node_id} tool",
        inputSchema={parameter: {"type": "string", "required": True}},
        forwardTemplate='{"%s":"{{direct_input.parameters.%s}}"}' % (forward_key, parameter),
    )


def _workflow(mode_forward_key: str = "source.mode") -> dict:
    """An agent with a search tool and a tool that saves the conversation mode."""
    results_template = "Results for {{source.query}} in {{session.mode}} mode"
    saved_mode = {"key": "mode", "value": "{{%s}}" % mode_forward_key}
    return {
        "id": "wf-acme",
        "nodes": [
            _node("agent", "agentNode", name="Acme assistant"),
            _tool("search", "query", "source.query"),
            _node("results", "templateNode", name="Search results", template=results_template),
            _tool("change_mode", "mode", mode_forward_key),
            _node("save_mode", "setStateNode", name="Save mode", states=[saved_mode]),
        ],
        "edges": [
            _edge("search", "agent", "output_tool", "input_tools"),
            _edge("search", "results", "starter_processor"),
            _edge("change_mode", "agent", "output_tool", "input_tools"),
            _edge("change_mode", "save_mode", "starter_processor"),
        ],
    }


def _agent_tools(workflow: dict):
    """The agent's tools by node id, and the run state of one customer message."""
    engine = WorkflowEngine(workflow)
    state = WorkflowState(
        workflow=engine.get_workflow(), thread_id=THREAD_ID, initial_values=dict(SESSION_AT_START)
    )
    tools = engine.executable_node("agent", state).get_connected_nodes("tools")
    return {tool.node_id: tool for tool in tools}, state


@pytest.fixture(autouse=True)
def saved_values_memory():
    """Keeps saved values in process instead of the conversation store."""
    with patch.object(SetStateNode, "get_memory", return_value=InMemoryConversationMemory(THREAD_ID)):
        yield


@pytest.mark.asyncio
async def test_each_call_of_a_tool_gets_its_own_arguments():
    tools, _ = _agent_tools(_workflow())

    answers = [await tools["search"].invoke(query=query) for query in QUERIES]

    assert answers == [f"Results for {query} in standard mode" for query in QUERIES]


@pytest.mark.asyncio
async def test_a_tool_call_leaves_its_arguments_out_of_the_session():
    tools, state = _agent_tools(_workflow())

    await tools["search"].invoke(query=QUERIES[0])

    assert state.get_session() == SESSION_AT_START


@pytest.mark.asyncio
@pytest.mark.parametrize("mode_forward_key", ["source.mode", "mode"])
async def test_a_value_saved_inside_a_tool_reaches_the_session(mode_forward_key):
    tools, state = _agent_tools(_workflow(mode_forward_key))

    await tools["change_mode"].invoke(mode="refund")

    assert state.get_session()["mode"] == "refund"


@pytest.mark.asyncio
async def test_the_next_tool_call_sees_a_value_saved_by_an_earlier_one():
    tools, _ = _agent_tools(_workflow())

    await tools["change_mode"].invoke(mode="refund")
    answer = await tools["search"].invoke(query=QUERIES[0])

    assert answer == f"Results for {QUERIES[0]} in refund mode"
