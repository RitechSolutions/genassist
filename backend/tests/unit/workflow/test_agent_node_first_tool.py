"""The agent step passes "Always call this tool first" to the agent, or warns why it could not"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.agents.sub_agents.models import SUB_AGENT_RESUME_KEY
from app.modules.workflow.engine.nodes.agent_node import AgentNode
from tests.unit.workflow.test_agent_node_delegation import _AGENT_ONCE, _Tool, _env, _parent_node, _rr

LONG_TOOL = "knowledge_base_for_help-centre_articles"
TOOLS = [_Tool("knowledge_base"), _Tool(LONG_TOOL), _Tool("save_note")]


def _state():
    return SimpleNamespace(
        set_node_input=MagicMock(),
        workflow={"nodes": [], "edges": []},
        initial_values={},
        get_memory=MagicMock(return_value=None),
        get_session=MagicMock(return_value={}),
        annotate_node_execution=MagicMock(),
    )


async def _process(config: dict, tools=TOOLS, delegation=([], {})):
    state = _state()
    node = AgentNode("node-1", {"type": "agentNode", "data": {}}, state)
    run_once = AsyncMock(return_value=_rr("answer"))
    with patch(_AGENT_ONCE, run_once), patch.object(AgentNode, "get_connected_nodes", return_value=list(tools)), \
            patch.object(AgentNode, "_build_delegation_tools", return_value=delegation):
        await node.process({"providerId": "prov-1", "memory": False, **config})
    return run_once.await_args.kwargs["first_tool"], state.annotate_node_execution


def _returns_directly(name: str) -> _Tool:
    tool = _Tool(name)
    tool.return_direct = True
    return tool


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("written", "expected"),
    [("Knowledge base", "knowledge_base"), (LONG_TOOL, LONG_TOOL), (f"  {LONG_TOOL} ", LONG_TOOL)],
    ids=["display name", "tool name", "surrounding spaces"],
)
async def test_a_connected_tool_is_passed_to_the_agent(written, expected):
    first_tool, annotate = await _process({"type": "ReActAgentLC", "firstTool": written})

    assert first_tool == expected
    annotate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("written", [None, "", "   "], ids=repr)
async def test_an_empty_setting_lets_the_agent_decide(written):
    first_tool, annotate = await _process({"type": "ReActAgentLC", "firstTool": written})

    assert first_tool is None
    annotate.assert_not_called()


@pytest.mark.asyncio
async def test_a_tool_that_is_not_connected_is_skipped_with_a_warning():
    first_tool, annotate = await _process({"type": "ReActAgentLC", "firstTool": "Order lookup"})

    assert first_tool is None
    warning = annotate.call_args.kwargs["warnings"][0]
    assert "'Order lookup'" in warning and "not a tool connected to this agent" in warning


@pytest.mark.asyncio
async def test_a_tool_that_returns_its_result_directly_is_skipped_with_a_warning():
    tools = [*TOOLS, _returns_directly("order_lookup")]

    first_tool, annotate = await _process({"type": "ReActAgentLC", "firstTool": "Order lookup"}, tools=tools)

    assert first_tool is None
    assert "ends the agent's turn" in annotate.call_args.kwargs["warnings"][0]


@pytest.mark.asyncio
async def test_a_sub_agent_hand_off_is_skipped_with_a_warning():
    delegation = ([_Tool("request_task_child")], {"request_task_child": {"child_node_id": "child"}})

    first_tool, annotate = await _process(
        {"type": "ReActAgentLC", "firstTool": "request_task_child"}, delegation=delegation
    )

    assert first_tool is None
    assert "ends the agent's turn" in annotate.call_args.kwargs["warnings"][0]


@pytest.mark.asyncio
async def test_another_agent_type_is_skipped_with_a_warning():
    first_tool, annotate = await _process({"type": "ToolSelector", "firstTool": "Knowledge base"})

    assert first_tool is None
    assert "works only with the ReActAgentLC agent type" in annotate.call_args.kwargs["warnings"][0]


async def _delegation_runs(node, results):
    with patch(_AGENT_ONCE, AsyncMock(side_effect=results)) as run_once:
        await node._run_agent_with_delegations(
            config={"piiMasking": False}, provider_id="p", fallback_chain_id=None, agent_type="ReActAgentLC",
            system_prompt="s", prompt="q", all_tools=[_Tool("request_task_child"), _Tool("knowledge_base")],
            delegation_map={"request_task_child": {"child_node_id": "child", "mode": "single_turn"}},
            max_iterations=7, chat_history=[], first_tool="knowledge_base",
        )
    return [call.kwargs["first_tool"] for call in run_once.await_args_list]


@pytest.mark.asyncio
async def test_with_sub_agents_the_tool_is_called_first_only_on_the_users_message():
    results = [
        _rr(_env("completed", "child answer"), return_direct=True, tool="request_task_child"),
        _rr("final answer"),
    ]

    assert await _delegation_runs(_parent_node(), results) == ["knowledge_base", None]


@pytest.mark.asyncio
async def test_a_resumed_turn_after_a_sub_agent_does_not_call_it_again():
    node = _parent_node()
    resumed = (0, [], [], "continue")
    node.get_state().initial_values[SUB_AGENT_RESUME_KEY] = {"marker": True}
    with patch.object(AgentNode, "_apply_sub_agent_resume", return_value=resumed):
        runs = await _delegation_runs(node, [_rr("final answer")])

    assert runs == [None]
