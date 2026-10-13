"""Unit tests for ReActAgentLC token-usage capture"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.errors import GraphRecursionError

from app.core.utils.llm_usage_utils import extract_usage_from_aimessage
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.react_agent_lc import ReActAgentLC
from app.modules.workflow.llm.prompt_caching_chat_model import (
    PromptCachingChatModel,
    build_cacheable_system_message,
)

_CREATE_AGENT = "app.modules.workflow.agents.react_agent_lc.create_agent"
_EXTRACT_USAGE = "app.modules.workflow.agents.react_agent_lc.extract_usage_from_aimessage"
_STABLE = "You are a helpful agent with a long stable prefix."
_SUFFIX = " Current time: 2026-08-17 12:00:00"


def _build_agent(fake_result=None, system_prompt="you are a helpful agent", error=None):
    with patch(_CREATE_AGENT, return_value=MagicMock()):
        agent = ReActAgentLC(
            llm_model=MagicMock(),
            system_prompt=system_prompt,
            tools=[],
        )

    async def _astream(input_data, config=None, **kwargs):
        if fake_result is not None:
            yield fake_result
        if error is not None:
            raise error

    agent.agent_executor.astream = _astream
    return agent


@pytest.mark.asyncio
async def test_collects_usage_per_generated_aimessage():
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "search", "args": {"q": "x"}, "id": "call_1", "type": "tool_call"}],
        usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
    )
    tool_msg = ToolMessage(content="tool output", tool_call_id="call_1")
    final_msg = AIMessage(
        content="the final answer",
        usage_metadata={"input_tokens": 30, "output_tokens": 5, "total_tokens": 35},
    )
    fake_result = {"messages": [HumanMessage(content="hi"), tool_call_msg, tool_msg, final_msg]}

    agent = _build_agent(fake_result)
    result = await agent.invoke("hi")

    assert result["status"] == "success"
    assert result["llm_usage"] == [
        {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        {"input_tokens": 30, "output_tokens": 5, "total_tokens": 35},
    ]


@pytest.mark.asyncio
async def test_no_llm_usage_key_when_no_usage_reported():
    final_msg = AIMessage(content="the final answer")
    fake_result = {"messages": [HumanMessage(content="hi"), final_msg]}

    agent = _build_agent(fake_result)
    result = await agent.invoke("hi")

    assert result["status"] == "success"
    assert "llm_usage" not in result


@pytest.mark.asyncio
async def test_a_message_whose_usage_cannot_be_read_does_not_fail_the_run():
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{"name": "search", "args": {"q": "x"}, "id": "call_1", "type": "tool_call"}],
        usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
    )
    tool_msg = ToolMessage(content="tool output", tool_call_id="call_1")
    final_msg = AIMessage(
        content="the final answer",
        usage_metadata={"input_tokens": 30, "output_tokens": 5, "total_tokens": 35},
    )
    fake_result = {"messages": [HumanMessage(content="hi"), tool_call_msg, tool_msg, final_msg]}

    def read_usage(message):
        if message is tool_call_msg:
            raise ValueError("unreadable usage payload")
        return extract_usage_from_aimessage(message)

    agent = _build_agent(fake_result)
    with patch(_EXTRACT_USAGE, side_effect=read_usage):
        result = await agent.invoke("hi")

    assert result["status"] == "success"
    assert result["response"] == "the final answer"
    assert result["llm_usage"] == [{"input_tokens": 30, "output_tokens": 5, "total_tokens": 35}]


@pytest.mark.asyncio
async def test_a_run_that_raises_mid_loop_still_reports_the_calls_it_made():
    first_call = AIMessage(
        content="",
        tool_calls=[{"name": "search", "args": {}, "id": "call_1", "type": "tool_call"}],
        usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
    )
    tool_msg = ToolMessage(content="tool output", tool_call_id="call_1")
    second_call = AIMessage(
        content="",
        tool_calls=[{"name": "search", "args": {}, "id": "call_2", "type": "tool_call"}],
        usage_metadata={"input_tokens": 30, "output_tokens": 5, "total_tokens": 35},
    )
    fake_result = {"messages": [HumanMessage(content="hi"), first_call, tool_msg, second_call]}

    agent = _build_agent(fake_result, error=GraphRecursionError("Recursion limit of 11 reached"))
    result = await agent.invoke("hi")

    assert result["status"] == "error"
    assert result["error"] == "Recursion limit of 11 reached"
    assert result["llm_usage"] == [
        {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
        {"input_tokens": 30, "output_tokens": 5, "total_tokens": 35},
    ]


@pytest.mark.asyncio
async def test_a_run_that_raises_before_any_state_reports_no_usage():
    agent = _build_agent(error=RuntimeError("boom"))
    result = await agent.invoke("hi")

    assert result["status"] == "error"
    assert result["error"] == "boom"
    assert "llm_usage" not in result


@pytest.mark.parametrize(
    "system_prompt",
    ["you are a helpful agent", SystemMessage(content=[{"type": "text", "text": "stable prefix"}])],
    ids=["str", "system_message"],
)
def test_create_agent_receives_the_system_prompt_unchanged(system_prompt):
    with patch(_CREATE_AGENT, return_value=MagicMock()) as create_agent:
        ReActAgentLC(llm_model=MagicMock(), system_prompt=system_prompt, tools=[])

    assert create_agent.call_args.kwargs["system_prompt"] is system_prompt


@pytest.mark.asyncio
async def test_stream_input_carries_no_system_message():
    agent = _build_agent({"messages": [AIMessage(content="done")]})
    seen = {}

    async def _astream(input_data, config=None, **kwargs):
        seen["messages"] = input_data["messages"]
        for chunk in ():
            yield chunk

    agent.agent_executor.astream = _astream

    async for _ in agent.stream("hi", chat_history=[{"role": "user", "content": "earlier"}]):
        pass

    assert not any(isinstance(message, SystemMessage) for message in seen["messages"])
    assert seen["messages"][-1] == HumanMessage(content="hi")


class _CapturingModel(BaseChatModel):
    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "capturing"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="the answer"))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


def _two_block_system_message() -> SystemMessage:
    return build_cacheable_system_message(_STABLE, _SUFFIX)


@pytest.mark.asyncio
async def test_a_real_graph_run_returns_the_model_reply():
    agent = ReActAgentLC(llm_model=_CapturingModel(), system_prompt="sys", tools=[])

    result = await agent.invoke("hi")

    assert result["status"] == "success"
    assert result["response"] == "the answer"


class _AlwaysCallsToolModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "always-calls-tool"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        message = AIMessage(
            content="",
            tool_calls=[{"name": "search", "args": {}, "id": f"call_{len(messages)}", "type": "tool_call"}],
            usage_metadata={"input_tokens": 10, "output_tokens": 1, "total_tokens": 11},
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


@pytest.mark.asyncio
async def test_a_real_graph_run_that_hits_the_recursion_limit_reports_every_call():
    async def search(_inp):
        return "still pending"

    tool = BaseTool(node_id="tool-1", name="search", description="d", parameters={}, function=search)
    agent = ReActAgentLC(llm_model=_AlwaysCallsToolModel(), system_prompt="sys", tools=[tool], max_iterations=2)

    result = await agent.invoke("hi")

    assert result["status"] == "error"
    assert result["error"].startswith("Recursion limit of 5 reached")
    assert result["llm_usage"] == [{"input_tokens": 10, "output_tokens": 1, "total_tokens": 11}] * 3


@pytest.mark.asyncio
class TestBlockSystemPromptReachesTheModel:
    @staticmethod
    def _agent(system_prompt):
        inner = _CapturingModel()
        llm = PromptCachingChatModel(inner=inner, cache_style="anthropic")
        return ReActAgentLC(llm_model=llm, system_prompt=system_prompt, tools=[]), inner

    async def test_marker_lands_on_the_stable_block_only(self):
        system_message = _two_block_system_message()
        agent, inner = self._agent(system_message)

        await agent.invoke("hi")

        assert inner.seen[-1][0].content == [
            {"type": "text", "text": _STABLE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": _SUFFIX},
        ]

    async def test_rendered_text_matches_the_plain_string_form(self):
        system_message = _two_block_system_message()
        agent, inner = self._agent(system_message)

        await agent.invoke("hi")

        blocks = inner.seen[-1][0].content
        assert "".join(block["text"] for block in blocks) == _STABLE + _SUFFIX

    async def test_repeated_turns_never_stack_markers(self):
        system_message = _two_block_system_message()
        agent, inner = self._agent(system_message)

        await agent.invoke("hi")
        await agent.invoke("hi again")

        for sent in inner.seen:
            assert sum("cache_control" in block for block in sent[0].content) == 1
        assert system_message.content == [
            {"type": "text", "text": _STABLE},
            {"type": "text", "text": _SUFFIX},
        ]

    async def test_string_system_prompt_is_never_marked(self):
        agent, inner = self._agent(_STABLE + _SUFFIX)

        await agent.invoke("hi")

        assert inner.seen[-1][0].content == _STABLE + _SUFFIX
