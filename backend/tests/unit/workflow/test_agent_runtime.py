"""Unit tests for the shared agent runtime (``run_agent_once``)"""

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import SystemMessage

from app.modules.workflow.agents.agent_runtime import AgentRunResult, run_agent_once
from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel
from app.modules.workflow.llm.prompt_caching_chat_model import (
    PROMPT_CACHE_OPT_IN_KEY,
    PromptCachingChatModel,
)

_RUNTIME = "app.modules.workflow.agents.agent_runtime"
_MERGE = "app.modules.workflow.engine.llm_usage_tracking.merge_llm_usage_from_result"
_AGENT_NAMES = ("ReActAgent", "ReActAgentLC", "SimpleToolAgent", "ToolAgent")
_SUFFIX = " Current time: 2026-08-17 12:00:00"
_PARTS = ("base prompt", _SUFFIX)


def _fake_agent_class(result):
    instance = MagicMock()
    instance.invoke = AsyncMock(return_value=result)
    instance.cache_split_decision = (False, None)
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

    merge.assert_awaited_once_with(state, result, "node-1", "prov-1", False)


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
    cls.assert_called_once_with(
        llm_model="reused-model", system_prompt="sys", tools=[], max_iterations=7,
        stable_volatile_parts=None, stable_tool_names=None,
    )


@pytest.mark.asyncio
async def test_tool_agent_receives_the_prompt_parts():
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    with stack:
        await run_agent_once(**_base_kwargs(stable_volatile_parts=_PARTS))

    cls, _ = classes["ToolAgent"]
    assert cls.call_args.kwargs["stable_volatile_parts"] == _PARTS


@pytest.mark.asyncio
async def test_tool_agent_receives_the_stable_tool_names():
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    names = frozenset({"weather"})
    with stack:
        await run_agent_once(**_base_kwargs(stable_tool_names=names))

    cls, _ = classes["ToolAgent"]
    assert cls.call_args.kwargs["stable_tool_names"] == names


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "agent_type,expected",
    [
        ("ReActAgent", "ReActAgent"),
        ("ReActAgentLC", "ReActAgentLC"),
        ("SimpleToolExecutor", "SimpleToolAgent"),
    ],
)
async def test_other_agents_never_receive_the_parts(agent_type, expected):
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    with stack:
        await run_agent_once(
            **_base_kwargs(
                agent_type=agent_type,
                stable_volatile_parts=_PARTS,
                stable_tool_names=frozenset({"weather"}),
            )
        )

    cls, _ = classes[expected]
    assert "stable_volatile_parts" not in cls.call_args.kwargs
    assert "stable_tool_names" not in cls.call_args.kwargs


def _caching_model():
    return PromptCachingChatModel(inner=MagicMock(name="inner-model"), cache_style="anthropic")


async def _react_lc_prompt(**overrides):
    """The system_prompt ReActAgentLC was constructed with"""
    stack, classes, _, _ = _patch_runtime({"response": "ok"})
    with stack:
        await run_agent_once(**_base_kwargs(agent_type="ReActAgentLC", **overrides))

    cls, _ = classes["ReActAgentLC"]
    return cls.call_args.kwargs["system_prompt"]


@pytest.mark.asyncio
class TestReActAgentLCSplit:
    async def test_cacheable_parts_become_two_blocks(self):
        prompt = await _react_lc_prompt(
            llm_model=_caching_model(), system_prompt="base prompt" + _SUFFIX, stable_volatile_parts=_PARTS
        )

        assert isinstance(prompt, SystemMessage)
        assert prompt.content == [
            {"type": "text", "text": "base prompt"},
            {"type": "text", "text": _SUFFIX},
        ]
        assert prompt.additional_kwargs == {PROMPT_CACHE_OPT_IN_KEY: True}

    async def test_blocks_render_back_to_the_original_string(self):
        prompt = await _react_lc_prompt(
            llm_model=_caching_model(), system_prompt="base prompt" + _SUFFIX, stable_volatile_parts=_PARTS
        )

        assert "".join(block["text"] for block in prompt.content) == "base prompt" + _SUFFIX

    async def test_model_without_caching_keeps_the_string(self):
        prompt = await _react_lc_prompt(system_prompt="base prompt" + _SUFFIX, stable_volatile_parts=_PARTS)

        assert prompt == "base prompt" + _SUFFIX

    async def test_missing_parts_keep_the_string(self):
        prompt = await _react_lc_prompt(llm_model=_caching_model(), system_prompt="base prompt" + _SUFFIX)

        assert prompt == "base prompt" + _SUFFIX

    @pytest.mark.parametrize("base", ["", " ", "\n\t "], ids=repr)
    async def test_blank_base_keeps_the_string(self, base):
        prompt = await _react_lc_prompt(
            llm_model=_caching_model(), system_prompt=base + _SUFFIX, stable_volatile_parts=(base, _SUFFIX)
        )

        assert prompt == base + _SUFFIX

    async def test_mixed_fallback_chain_keeps_the_string(self):
        chain = FallbackChatModel(models=[MagicMock(name="plain"), _caching_model()])
        prompt = await _react_lc_prompt(
            llm_model=chain, system_prompt="base prompt" + _SUFFIX, stable_volatile_parts=_PARTS
        )

        assert prompt == "base prompt" + _SUFFIX

    async def test_homogeneous_fallback_chain_splits(self):
        chain = FallbackChatModel(models=[_caching_model(), _caching_model()])
        prompt = await _react_lc_prompt(
            llm_model=chain, system_prompt="base prompt" + _SUFFIX, stable_volatile_parts=_PARTS
        )

        assert isinstance(prompt, SystemMessage)


@pytest.mark.asyncio
class TestPromptCachingOptIn:

    @pytest.mark.parametrize("requested", [True, False], ids=["opted-in", "default-off"])
    async def test_the_request_reaches_the_model_build(self, requested):
        stack, _, injector, _ = _patch_runtime({"response": "ok"})
        with stack:
            await run_agent_once(**_base_kwargs(prompt_caching_enabled=requested))

        provider = injector.get.return_value
        assert provider.get_model_for_node.await_args.args == ("prov-1", None, requested)

    @pytest.mark.parametrize("requested", [True, False], ids=["opted-in", "default-off"])
    async def test_the_request_marks_the_usage_merge(self, requested):
        stack, _, _, merge = _patch_runtime({"response": "ok"})
        with stack:
            await run_agent_once(**_base_kwargs(prompt_caching_enabled=requested))

        assert merge.await_args.args[-1] is requested

    async def test_a_reused_model_skips_the_build_but_still_marks_usage(self):
        stack, _, injector, merge = _patch_runtime({"response": "ok"})
        with stack:
            await run_agent_once(**_base_kwargs(llm_model="reused-model", prompt_caching_enabled=True))

        injector.get.assert_not_called()
        assert merge.await_args.args[-1] is True

    async def test_omitting_the_argument_defaults_to_off(self):
        stack, _, injector, _ = _patch_runtime({"response": "ok"})
        with stack:
            await run_agent_once(**_base_kwargs())

        assert injector.get.return_value.get_model_for_node.await_args.args == ("prov-1", None, False)


class _DiagState:

    def __init__(self):
        self.prompt_caching_diagnostics: dict = {}


async def _diagnose(*, tool_agent_split=None, result=None, **overrides):
    state = _DiagState()
    stack, classes, _, _ = _patch_runtime(result if result is not None else {"response": "ok"})
    if tool_agent_split is not None:
        classes["ToolAgent"][1].cache_split_decision = (tool_agent_split, None)
    with stack:
        await run_agent_once(**_base_kwargs(state=state, prompt_caching_enabled=True, **overrides))
    return state.prompt_caching_diagnostics.get("node-1")


@pytest.mark.asyncio
class TestDiagnosticPerDispatchBranch:

    @pytest.mark.parametrize("agent_type", ["ReActAgent", "SimpleToolExecutor"])
    async def test_a_mode_that_never_splits_says_so(self, agent_type):
        diagnostic = await _diagnose(
            agent_type=agent_type, llm_model=_caching_model(), stable_volatile_parts=_PARTS
        )

        assert diagnostic == {"requested": True, "applied": False}

    async def test_react_lc_applied_tracks_the_split_it_actually_got(self):
        diagnostic = await _diagnose(
            agent_type="ReActAgentLC",
            llm_model=_caching_model(),
            system_prompt="base prompt" + _SUFFIX,
            stable_volatile_parts=_PARTS,
        )

        assert diagnostic == {"requested": True, "applied": True}

    async def test_react_lc_without_parts_is_withheld(self):
        diagnostic = await _diagnose(agent_type="ReActAgentLC", llm_model=_caching_model())

        assert diagnostic == {"requested": True, "applied": False}

    @pytest.mark.parametrize("base", ["", "  \n"], ids=repr)
    async def test_react_lc_with_a_blank_stable_half_is_withheld(self, base):
        diagnostic = await _diagnose(
            agent_type="ReActAgentLC",
            llm_model=_caching_model(),
            system_prompt=base + _SUFFIX,
            stable_volatile_parts=(base, _SUFFIX),
        )

        assert diagnostic == {"requested": True, "applied": False}

    async def test_react_lc_on_a_plain_model_is_withheld(self):
        diagnostic = await _diagnose(agent_type="ReActAgentLC", stable_volatile_parts=_PARTS)

        assert diagnostic == {"requested": True, "applied": False}

    async def test_react_lc_on_a_mixed_chain_is_withheld(self):
        chain = FallbackChatModel(models=[MagicMock(name="plain"), _caching_model()])
        diagnostic = await _diagnose(agent_type="ReActAgentLC", llm_model=chain, stable_volatile_parts=_PARTS)

        assert diagnostic == {"requested": True, "applied": False}

    @pytest.mark.parametrize("split", [True, False], ids=["split", "fused"])
    async def test_tool_agent_applied_mirrors_its_own_decision(self, split):
        diagnostic = await _diagnose(
            tool_agent_split=split, llm_model=_caching_model(), stable_volatile_parts=_PARTS
        )

        assert diagnostic["applied"] is split

    async def test_an_unexplained_withheld_split_still_records(self):
        diagnostic = await _diagnose(
            tool_agent_split=False, llm_model=_caching_model(), stable_volatile_parts=_PARTS
        )

        assert diagnostic == {"requested": True, "applied": False}


@pytest.mark.asyncio
class TestARaisingInvocationRecordsNoAppliedMarker:

    async def test_an_applied_split_leaves_no_diagnostic_when_the_agent_raises(self):
        state = _DiagState()
        stack, classes, _, _ = _patch_runtime({"response": "ok"})
        classes["ToolAgent"][1].cache_split_decision = (True, None)
        classes["ToolAgent"][1].invoke.side_effect = RuntimeError("provider down")

        with stack:
            with pytest.raises(RuntimeError):
                await run_agent_once(**_base_kwargs(state=state, prompt_caching_enabled=True))

        assert state.prompt_caching_diagnostics == {}

    async def test_a_withheld_verdict_survives_the_raise(self):
        state = _DiagState()
        stack, classes, _, _ = _patch_runtime({"response": "ok"})
        classes["ToolAgent"][1].invoke.side_effect = RuntimeError("provider down")

        with stack:
            with pytest.raises(RuntimeError):
                await run_agent_once(**_base_kwargs(state=state, prompt_caching_enabled=True))

        assert state.prompt_caching_diagnostics == {"node-1": {"requested": True, "applied": False}}


@pytest.mark.asyncio
class TestTheEntryStaysFlagOnly:

    async def test_an_applied_run_records_the_flags_only(self):
        result = {
            "response": "ok",
            "llm_usage": [
                {"input_tokens": 5, "output_tokens": 2, "token_details": {"cache_read": 900, "cache_creation": 100}},
            ],
        }
        diagnostic = await _diagnose(tool_agent_split=True, result=result)

        assert diagnostic == {"requested": True, "applied": True}

    async def test_a_withheld_split_never_gains_token_fields(self):
        result = {
            "response": "ok",
            "llm_usage": [{"input_tokens": 5, "output_tokens": 2, "token_details": {"cache_read": 900}}],
        }
        diagnostic = await _diagnose(tool_agent_split=False, result=result)

        assert diagnostic == {"requested": True, "applied": False}


@pytest.mark.asyncio
class TestAnErrorResultRecordsNoAppliedMarker:

    async def test_an_error_with_no_usage_leaves_no_diagnostic(self):
        diagnostic = await _diagnose(tool_agent_split=True, result={"status": "error", "response": "boom"})

        assert diagnostic is None

    async def test_an_error_after_real_calls_still_records_applied(self):
        result = {
            "status": "error",
            "response": "max iterations reached",
            "llm_usage": [{"input_tokens": 5, "output_tokens": 2}],
        }
        diagnostic = await _diagnose(tool_agent_split=True, result=result)

        assert diagnostic == {"requested": True, "applied": True}

    async def test_a_withheld_verdict_survives_an_error_result(self):
        diagnostic = await _diagnose(tool_agent_split=False, result={"status": "error", "response": "boom"})

        assert diagnostic == {"requested": True, "applied": False}


@pytest.mark.asyncio
class TestDiagnosticIsRequestGated:

    async def test_an_unrequested_run_writes_nothing(self):
        state = _DiagState()
        stack, _, _, _ = _patch_runtime({"response": "ok"})
        with stack:
            await run_agent_once(**_base_kwargs(state=state, agent_type="ReActAgent"))

        assert state.prompt_caching_diagnostics == {}

    async def test_a_state_without_the_hook_never_breaks_the_run(self):
        stack, _, _, _ = _patch_runtime({"response": "ok"})
        with stack:
            run = await run_agent_once(
                **_base_kwargs(state=SimpleNamespace(), agent_type="ReActAgent", prompt_caching_enabled=True)
            )

        assert run.response == "ok"

    async def test_repeated_runs_stay_idempotent(self):
        state = _DiagState()
        stack, _, _, _ = _patch_runtime({"response": "ok"})
        with stack:
            for _ in range(3):
                await run_agent_once(
                    **_base_kwargs(state=state, agent_type="ReActAgent", prompt_caching_enabled=True)
                )

        assert state.prompt_caching_diagnostics == {"node-1": {"requested": True, "applied": False}}
