"""SubAgentNode: clean output, completion tools, config validation, engine halt"""

from unittest.mock import AsyncMock, patch

import pytest

from app.modules.workflow.agents.agent_runtime import AgentRunResult
from app.modules.workflow.agents.memory import InMemoryConversationMemory
from app.modules.workflow.agents.sub_agents.orchestrator import SUB_AGENT_CONTROL_ATTR
from app.modules.workflow.engine.nodes.sub_agent_node import SubAgentNode
from app.modules.workflow.engine.workflow_engine import WorkflowEngine, _sanitize_output_for_memory
from app.modules.workflow.engine.workflow_state import WorkflowState

_NODE = "app.modules.workflow.engine.nodes.sub_agent_node"


def _make_node(config_extra=None, thread_id="t-sub"):
    workflow = {"config": {"id": "wf1"}, "nodes": [{"id": "child", "type": "subAgentNode", "data": {}}], "edges": []}
    state = WorkflowState(workflow=workflow, thread_id=thread_id, initial_values={"message": "hi"})
    state.memory = InMemoryConversationMemory(thread_id)
    state.node_execution_status["child"] = {}
    return SubAgentNode("child", {"type": "subAgentNode", "data": {"name": "Helper"}}, state)


_OK_CONFIG = {"providerId": "prov-1", "mode": "single_turn", "timeoutSeconds": 120}


def _run_result(**over):
    base = dict(
        response="answer",
        steps=[{"s": 1}],
        tools_used=["t"],
        status="success",
        error=None,
        raw={"response": "answer"},
        llm_model="m",
    )
    base.update(over)
    return AgentRunResult(**base)


@pytest.mark.asyncio
async def test_single_turn_returns_clean_output_only():
    node = _make_node()
    with (
        patch(f"{_NODE}.run_agent_once", AsyncMock(return_value=_run_result())),
        patch.object(SubAgentNode, "get_connected_nodes", return_value=[]),
    ):
        output = await node.process(dict(_OK_CONFIG))

    assert output == {"message": "answer", "steps": [{"s": 1}], "tools_used": ["t"]}
    for control_key in ("sub_agent_status", "next_nodes", "sub_agent", "status"):
        assert control_key not in output


@pytest.mark.asyncio
async def test_missing_provider_returns_error():
    node = _make_node()
    with patch.object(SubAgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process({"mode": "single_turn"})
    assert output["error"] == "missing providerId"


@pytest.mark.asyncio
async def test_invalid_mode_returns_error():
    node = _make_node()
    with patch.object(SubAgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process({"providerId": "p", "mode": "bogus"})
    assert output["error"] == "invalid mode"


@pytest.mark.asyncio
async def test_timeout_out_of_range_returns_error():
    node = _make_node()
    with patch.object(SubAgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process({"providerId": "p", "mode": "task", "timeoutSeconds": 999})
    assert output["error"] == "timeout out of range"


@pytest.mark.asyncio
async def test_negative_timeout_returns_out_of_range_error():
    node = _make_node()
    with patch.object(SubAgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process({"providerId": "p", "mode": "task", "timeoutSeconds": -5})
    assert output["error"] == "timeout out of range"


@pytest.mark.asyncio
async def test_non_finite_timeout_returns_invalid_error():
    node = _make_node()
    with patch.object(SubAgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process({"providerId": "p", "mode": "task", "timeoutSeconds": float("inf")})
    assert output["error"] == "invalid timeoutSeconds"


@pytest.mark.asyncio
async def test_unsupported_agent_type_rejected_not_coerced():
    node = _make_node()
    with patch.object(SubAgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process({"providerId": "p", "mode": "single_turn", "type": "SimpleToolExecutor"})
    assert output["error"] == "invalid agent type"


def test_single_turn_has_no_completion_tool():
    assert _make_node()._build_completion_tool("single_turn") is None


@pytest.mark.asyncio
async def test_task_completion_tool_sets_marker():
    node = _make_node()
    tool = node._build_completion_tool("task")
    assert tool.name == "finish_task"
    result = await tool.invoke(result="the answer")
    assert result == "the answer"
    assert getattr(node.get_state(), SUB_AGENT_CONTROL_ATTR) == {"result": "the answer"}


def test_chat_completion_tool_named_return_to_parent():
    assert _make_node()._build_completion_tool("chat").name == "return_to_parent"


def test_pause_output_persisted_as_plain_message():
    pause = {"status": "awaiting_input", "sub_agent": {"message": "Is a layover okay?"}, "node_id": "p"}
    assert _sanitize_output_for_memory(pause) == "Is a layover okay?"


def test_sanitize_leaves_normal_and_hitl_output_untouched():
    assert _sanitize_output_for_memory({"message": "hi"}) == {"message": "hi"}
    form = {"status": "awaiting_input", "form_schema": {"fields": []}}
    assert _sanitize_output_for_memory(form) == form


def test_find_next_nodes_skips_output_sub_agent_edge():
    workflow = {
        "id": "wf1",
        "nodes": [{"id": "child", "type": "subAgentNode"}, {"id": "parent", "type": "agentNode"}],
        "edges": [
            {
                "source": "child",
                "target": "parent",
                "sourceHandle": "output_sub_agent",
                "targetHandle": "input_sub_agents",
            }
        ],
    }
    engine = WorkflowEngine(workflow)
    assert engine._find_next_nodes("child") == []
