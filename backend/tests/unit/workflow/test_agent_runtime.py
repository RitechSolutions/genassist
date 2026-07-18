"""Unit tests for the shared agent runtime (``run_agent_once``)"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.agents.agent_runtime import AgentRunResult, run_agent_once

_RUNTIME = "app.modules.workflow.agents.agent_runtime"
_MERGE = "app.modules.workflow.engine.llm_usage_tracking.merge_llm_usage_from_result"
_AGENT_NAMES = ("ReActAgent", "ReActAgentLC", "SimpleToolAgent", "ToolAgent")


def _fake_agent_class(result):
    instance = MagicMock()
    instance.invoke = AsyncMock(return_value=result)
    return MagicMock(return_value=instance), instance


def _fake_injector(model="resolved-model"):
    provider = MagicMock()
    provider.get_model_for_node = AsyncMock(return_value=model)
    injector = MagicMock()
    injector.get.return_value = provider
    return injector, provider


def _patch_runtime(result, model="resolved-model"):
    stack = ExitStack()
    classes = {}
    for name in _AGENT_NAMES:
        cls, instance = _fake_agent_class(result)
        classes[name] = (cls, instance)
        stack.enter_context(patch(f"{_RUNTIME}.{name}", cls))
    injector, _ = _fake_injector(model)
    stack.enter_context(patch("app.dependencies.injector.injector", injector))
    merge = AsyncMock()
    stack.enter_context(patch(_MERGE, merge))
    return stack, classes, injector, merge


def _base_kwargs(**overrides):
    kwargs = dict(
        state=SimpleNamespace(),
        node_id="node-1",
        provider_id="prov-1",
        fallback_chain_id=None,
        agent_type="ToolSelector",
        system_prompt="sys",
        user_prompt="hi",
        tools=[],
        max_iterations=7,
    )
    kwargs.update(overrides)
    return kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_type,expected",
    [
        ("ReActAgent", "ReActAgent"),
        ("ReActAgentLC", "ReActAgentLC"),
        ("SimpleToolExecutor", "SimpleToolAgent"),
        ("ToolSelector", "ToolAgent"),
        ("anything-else", "ToolAgent"),
    ],
)
async def test_selects_agent_class_per_type(agent_type, expected):
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    with stack:
        await run_agent_once(**_base_kwargs(agent_type=agent_type))

    for name, (cls, _instance) in classes.items():
        if name == expected:
            cls.assert_called_once()
        else:
            cls.assert_not_called()


@pytest.mark.asyncio
async def test_tool_and_react_agents_receive_max_iterations():
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    with stack:
        await run_agent_once(**_base_kwargs(agent_type="ReActAgent", max_iterations=3))

    cls, _ = classes["ReActAgent"]
    cls.assert_called_once_with(llm_model="resolved-model", system_prompt="sys", tools=[], max_iterations=3)


@pytest.mark.asyncio
async def test_simple_tool_agent_built_without_max_iterations():
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    with stack:
        await run_agent_once(**_base_kwargs(agent_type="SimpleToolExecutor"))

    cls, _ = classes["SimpleToolAgent"]
    cls.assert_called_once_with(llm_model="resolved-model", system_prompt="sys", tools=[])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_type,steps_key",
    [
        ("ReActAgent", "reasoning_steps"),
        ("ReActAgentLC", "reasoning_steps"),
        ("ToolSelector", "steps"),
        ("SimpleToolExecutor", "steps"),
    ],
)
async def test_steps_normalization_reads_the_right_key(agent_type, steps_key):
    result = {"response": "ok", "reasoning_steps": [{"r": 1}], "steps": [{"s": 2}]}
    stack, _, _, _ = _patch_runtime(result)
    with stack:
        run = await run_agent_once(**_base_kwargs(agent_type=agent_type))

    assert run.steps == result[steps_key]


@pytest.mark.asyncio
async def test_merges_usage_from_result():
    result = {"response": "ok"}
    stack, _, _, merge = _patch_runtime(result)
    state = SimpleNamespace()
    with stack:
        await run_agent_once(**_base_kwargs(state=state))

    merge.assert_awaited_once_with(state, result, "node-1", "prov-1")


@pytest.mark.asyncio
async def test_invoke_receives_prompt_and_history():
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    history = [{"role": "user", "content": "earlier"}]
    with stack:
        await run_agent_once(**_base_kwargs(user_prompt="hello", chat_history=history))

    _, instance = classes["ToolAgent"]
    instance.invoke.assert_awaited_once_with("hello", chat_history=history)


@pytest.mark.asyncio
async def test_missing_history_defaults_to_empty_list():
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    with stack:
        await run_agent_once(**_base_kwargs(chat_history=None))

    _, instance = classes["ToolAgent"]
    instance.invoke.assert_awaited_once_with("hi", chat_history=[])


@pytest.mark.asyncio
async def test_result_fields_mapped_and_raw_preserved():
    result = {
        "response": "Paris",
        "status": "success",
        "error": None,
        "tools_used": ["calc"],
        "steps": [{"s": 1}],
        "return_direct": True,
        "tool": "calc",
    }
    stack, _, _, _ = _patch_runtime(result)
    with stack:
        run = await run_agent_once(**_base_kwargs())

    assert isinstance(run, AgentRunResult)
    assert run.response == "Paris"
    assert run.status == "success"
    assert run.tools_used == ["calc"]
    assert run.steps == [{"s": 1}]
    assert run.llm_model == "resolved-model"
    assert run.raw is result


@pytest.mark.asyncio
async def test_supplied_llm_model_skips_provider_resolution():
    stack, classes, injector, _ = _patch_runtime({"response": "ok"})
    with stack:
        run = await run_agent_once(**_base_kwargs(llm_model="reused-model"))

    injector.get.assert_not_called()
    assert run.llm_model == "reused-model"
    cls, _ = classes["ToolAgent"]
    cls.assert_called_once_with(llm_model="reused-model", system_prompt="sys", tools=[], max_iterations=7)
