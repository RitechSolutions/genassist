"""AgentNode puts the context its tool-provider nodes read for the turn in front of the message"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.agents.agent_runtime import AgentRunResult
from app.modules.workflow.engine.nodes.agent_node import AgentNode

_AGENT_NODE = "app.modules.workflow.engine.nodes.agent_node"
_CONFIG = {"providerId": "prov-1", "type": "ReActAgentLC", "memory": False, "userPrompt": "Add a Slack step"}


def _state():
    return SimpleNamespace(
        set_node_input=MagicMock(),
        workflow={"nodes": [], "edges": []},
        initial_values={},
        get_memory=MagicMock(return_value=None),
        get_session=MagicMock(return_value={}),
    )


def _run_result():
    return AgentRunResult(response="ok", steps=[], tools_used=[], status="success", error=None, raw={}, llm_model="m")


class _Provider:
    def __init__(self, text=None, error=None):
        self.node_id = "tools"
        self._text = text
        self._error = error

    async def turn_context(self):
        if self._error:
            raise self._error
        return self._text


class _PlainTool:
    node_id = "plain"


async def _process(providers, tools=("a-tool",)):
    node = AgentNode("agent", {"type": "agentNode", "data": {"name": "Agent"}}, _state())
    once = AsyncMock(return_value=_run_result())
    with patch(f"{_AGENT_NODE}.run_agent_once", once), patch.object(
        AgentNode, "get_connected_nodes", return_value=list(tools)
    ), patch.object(AgentNode, "attached_tool_nodes", return_value=list(providers)) as attached:
        await node.process(dict(_CONFIG))
    return once.await_args.kwargs["user_prompt"], attached, node


@pytest.mark.asyncio
async def test_turn_context_goes_in_front_of_the_message():
    prompt, _, node = await _process([_Provider("WORKFLOW — 3 nodes\nn1 chatInputNode")])

    assert prompt == "WORKFLOW — 3 nodes\nn1 chatInputNode\n\nAdd a Slack step"
    # The execution record shows what the model saw.
    assert node.get_state().set_node_input.call_args.args[1]["prompt"] == prompt


@pytest.mark.asyncio
async def test_providers_without_context_and_failing_providers_leave_the_message_alone():
    prompt, _, _ = await _process([_PlainTool(), _Provider(""), _Provider(error=RuntimeError("redis down"))])

    assert prompt == "Add a Slack step"


@pytest.mark.asyncio
async def test_several_providers_are_joined_in_edge_order():
    prompt, _, _ = await _process([_Provider("first"), _Provider("  second  ")])

    assert prompt == "first\n\nsecond\n\nAdd a Slack step"


@pytest.mark.asyncio
async def test_an_agent_without_tools_never_looks_for_context():
    prompt, attached, _ = await _process([_Provider("ignored")], tools=())

    assert prompt == "Add a Slack step"
    attached.assert_not_called()


def test_attached_tool_nodes_follows_the_tools_edges_only():
    from app.modules.workflow.engine.nodes import WorkflowBuilderToolsNode
    from app.modules.workflow.engine.workflow_engine import WorkflowEngine

    WorkflowEngine({"nodes": [], "edges": []})  # populates the node registry
    workflow = {
        "nodes": [
            {"id": "agent", "type": "agentNode", "data": {}},
            {"id": "tools", "type": "workflowBuilderToolsNode", "data": {}},
            {"id": "start", "type": "chatInputNode", "data": {}},
            {"id": "ghost", "type": "noSuchNode", "data": {}},
        ],
        "edges": [],
    }
    state = SimpleNamespace(
        workflow=workflow,
        target_edges={
            "agent": [
                {"source": "start", "target": "agent", "sourceHandle": "output", "targetHandle": "input"},
                {"source": "tools", "target": "agent", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
                {"source": "ghost", "target": "agent", "sourceHandle": "output_tool", "targetHandle": "input_tools"},
            ]
        },
    )
    node = AgentNode("agent", {"type": "agentNode", "data": {}}, state)

    attached = node.attached_tool_nodes()

    assert [type(n) for n in attached] == [WorkflowBuilderToolsNode]
    assert attached[0].node_id == "tools"


def test_attached_tool_nodes_is_empty_when_the_state_has_no_edges():
    node = AgentNode("agent", {"type": "agentNode", "data": {}}, _state())
    assert node.attached_tool_nodes() == []


# ── Model requirements of attached tool providers ─────────────────────────


class _Demanding:
    node_id = "demanding"

    def __init__(self, floor=16000, error=None):
        self._floor, self._error = floor, error

    def model_requirements(self):
        if self._error:
            raise self._error
        return {"min_max_tokens": self._floor}


async def _floor_passed(providers, tools=("a-tool",)):
    node = AgentNode("agent", {"type": "agentNode", "data": {"name": "Agent"}}, _state())
    once = AsyncMock(return_value=_run_result())
    with patch(f"{_AGENT_NODE}.run_agent_once", once), patch.object(
        AgentNode, "get_connected_nodes", return_value=list(tools)
    ), patch.object(AgentNode, "attached_tool_nodes", return_value=list(providers)):
        await node.process(dict(_CONFIG))
    return once.await_args.kwargs["min_max_tokens"]


@pytest.mark.asyncio
async def test_the_highest_output_floor_of_the_attached_providers_reaches_the_model_choice():
    assert await _floor_passed([_PlainTool(), _Demanding(4000), _Demanding(16000)]) == 16000


@pytest.mark.asyncio
async def test_plain_tools_and_failing_providers_ask_for_no_floor():
    assert await _floor_passed([_PlainTool(), _Demanding(error=RuntimeError("boom")), _Demanding(0)]) is None
    assert await _floor_passed([_Demanding(16000)], tools=()) is None


def test_the_builder_tools_node_needs_room_for_its_plans():
    from app.modules.workflow.engine.nodes.workflow_builder_tools_node import MIN_MAX_TOKENS, WorkflowBuilderToolsNode

    node = WorkflowBuilderToolsNode("tools", {"type": "workflowBuilderToolsNode", "data": {}}, _state())
    assert node.model_requirements() == {"min_max_tokens": MIN_MAX_TOKENS}
    assert MIN_MAX_TOKENS >= 16000
