"""Byte-identical output shapes for AgentNode with no sub-agents attached"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.engine.nodes.agent_node import AgentNode

_RUNTIME = "app.modules.workflow.agents.agent_runtime"
_MERGE = "app.modules.workflow.engine.llm_usage_tracking.merge_llm_usage_from_result"


def _make_node():
    state = SimpleNamespace(set_node_input=MagicMock())
    node = AgentNode("node-1", {"type": "agentNode", "data": {"name": "Agent"}}, state)
    return node


def _patch_runtime(*, result=None, resolve_error=None):
    stack = ExitStack()

    instance = MagicMock()
    instance.invoke = AsyncMock(return_value=result or {})
    stack.enter_context(patch(f"{_RUNTIME}.ToolAgent", MagicMock(return_value=instance)))

    provider = MagicMock()
    if resolve_error is not None:
        provider.get_model_for_node = AsyncMock(side_effect=resolve_error)
    else:
        provider.get_model_for_node = AsyncMock(return_value="resolved-model")
    injector = MagicMock()
    injector.get.return_value = provider
    stack.enter_context(patch("app.dependencies.injector.injector", injector))

    stack.enter_context(patch(_MERGE, AsyncMock()))
    return stack, instance


_CONFIG = {"providerId": "prov-1", "type": "ToolSelector", "memory": False}


@pytest.mark.asyncio
async def test_success_shape():
    node = _make_node()
    stack, _ = _patch_runtime(result={"response": "Paris", "steps": [{"s": 1}], "tools_used": ["calc"]})
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {"message": "Paris", "steps": [{"s": 1}], "tools_used": ["calc"]}


@pytest.mark.asyncio
async def test_agent_internal_error_shape():
    node = _make_node()
    stack, _ = _patch_runtime(result={"status": "error", "error": "boom", "steps": [], "tools_used": []})
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {
        "message": "The agent could not complete your request: boom",
        "error": "boom",
        "steps": [],
        "tools_used": [],
    }


@pytest.mark.asyncio
async def test_raised_exception_shape():
    node = _make_node()
    stack, _ = _patch_runtime(resolve_error=RuntimeError("kaboom"))
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {
        "message": "The agent could not complete your request: kaboom",
        "error": "kaboom",
    }


@pytest.mark.asyncio
async def test_no_response_shape():
    node = _make_node()
    stack, _ = _patch_runtime(result={"response": None})
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {
        "message": "The agent did not return a response. Please try again or review the agent configuration.",
        "steps": [],
        "tools_used": [],
    }


@pytest.mark.asyncio
async def test_return_direct_result_flows_through_as_success():
    node = _make_node()
    stack, _ = _patch_runtime(
        result={
            "response": "direct answer",
            "return_direct": True,
            "tool": "some_tool",
            "parameters": {},
            "tools_used": ["some_tool"],
            "steps": [],
        }
    )
    with stack, patch.object(AgentNode, "get_connected_nodes", return_value=[]):
        output = await node.process(dict(_CONFIG))

    assert output == {"message": "direct answer", "steps": [], "tools_used": ["some_tool"]}


@pytest.mark.asyncio
async def test_memory_enabled_forwards_chat_history():
    node = _make_node()
    history = [{"role": "user", "content": "earlier"}]
    stack, instance = _patch_runtime(result={"response": "ok", "steps": [], "tools_used": []})
    with (
        stack,
        patch.object(AgentNode, "get_connected_nodes", return_value=[]),
        patch.object(AgentNode, "get_memory", return_value=MagicMock()),
        patch.object(AgentNode, "_get_chat_history_for_agent", AsyncMock(return_value=history)),
    ):
        await node.process({"providerId": "prov-1", "type": "ToolSelector", "memory": True})

    invoked_prompt, invoked_kwargs = instance.invoke.await_args
    assert invoked_kwargs["chat_history"] == history
