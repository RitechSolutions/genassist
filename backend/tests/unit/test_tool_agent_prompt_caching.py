"""ToolAgent's gated system/user split, and the fused payload it must preserve when off"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.modules.workflow.agents.agent_prompts import (
    create_conversation_context,
    create_tool_agent_no_tools_prompt,
    create_tool_agent_no_tools_query_prompt,
    create_tool_agent_tools_available_prompt,
    create_tool_agent_tools_query_prompt,
)
from app.modules.workflow.agents.agent_utils import create_tool_descriptions
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.modules.workflow.llm.prompt_caching_chat_model import PromptCachingChatModel

_BASE = "You are a helpful assistant with a long stable prefix."
_SUFFIX = " Current time: 2026-08-17 12:00:00"
_QUERY = "what is the weather?"
_HISTORY = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "noted"}]

_DIRECT_JSON = json.dumps({"action": "direct_response", "response": "It is sunny.", "reasoning": "known"})
_TOOL_CALL_JSON = json.dumps(
    {
        "action": "tool_call",
        "tool_name": "weather",
        "parameters": {"city": "Berlin"},
        "reasoning": "the user asked for weather",
    }
)


class _CapturingModel(BaseChatModel):

    seen: list = []
    replies: list = []

    @property
    def _llm_type(self) -> str:
        return "capturing"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        text = self.replies[len(self.seen) - 1] if len(self.seen) <= len(self.replies) else self.replies[-1]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)


def _weather_tool(result="Sunny, 21C"):
    return BaseTool(
        node_id="n1",
        name="weather",
        description="Look up the weather for a city.",
        parameters={"city": {"type": "string", "description": "City name", "required": True}},
        function=AsyncMock(return_value=result),
    )


def _agent(*, tools=None, replies=None, caching=True, suffix=_SUFFIX, system_prompt=None):
    inner = _CapturingModel(replies=replies or [_DIRECT_JSON])
    llm = PromptCachingChatModel(inner=inner, cache_style="anthropic") if caching else inner
    agent = ToolAgent(
        llm_model=llm,
        system_prompt=_BASE + _SUFFIX if system_prompt is None else system_prompt,
        tools=tools if tools is not None else [],
        volatile_system_suffix=suffix,
    )
    return agent, inner


def _fused_text(inner) -> str:
    sent = inner.seen[-1]
    assert len(sent) == 1
    return sent[0].content


def _split_turns(inner):
    sent = inner.seen[-1]
    assert isinstance(sent[0], SystemMessage)
    assert isinstance(sent[1], HumanMessage)
    return sent[0].content, sent[1].content


class TestGate:
    @pytest.mark.parametrize(
        "kwargs,expected",
        [
            ({}, True),
            ({"caching": False}, False),
            ({"suffix": None}, False),
            ({"suffix": ""}, False),
            ({"system_prompt": _BASE + _SUFFIX + " trailing"}, False),
        ],
        ids=["caching_and_suffix", "no_caching", "no_suffix", "empty_suffix", "suffix_not_at_end"],
    )
    def test_split_only_when_the_prompt_is_marked_cacheable(self, kwargs, expected):
        agent, _ = _agent(**kwargs)

        assert agent._cache_split is expected


@pytest.mark.asyncio
class TestFusedModeIsUnchanged:
    async def test_no_tools_sends_the_original_single_user_turn(self):
        agent, inner = _agent(caching=False)

        await agent.invoke(_QUERY, chat_history=_HISTORY)

        expected = create_tool_agent_no_tools_query_prompt(
            create_tool_agent_no_tools_prompt(_BASE + _SUFFIX),
            create_conversation_context(_HISTORY),
            _QUERY,
        )
        assert _fused_text(inner) == expected

    async def test_tools_send_the_original_single_user_turn(self):
        tool = _weather_tool()
        agent, inner = _agent(tools=[tool], caching=False)

        await agent.invoke(_QUERY, chat_history=_HISTORY)

        expected = create_tool_agent_tools_query_prompt(
            create_tool_agent_tools_available_prompt(_BASE + _SUFFIX, create_tool_descriptions([tool])),
            create_conversation_context(_HISTORY),
            _QUERY,
        )
        assert _fused_text(inner) == expected

    async def test_caching_model_without_a_suffix_stays_fused_and_unmarked(self):
        agent, inner = _agent(tools=[_weather_tool()], suffix=None)

        await agent.invoke(_QUERY)

        assert isinstance(_fused_text(inner), str)


@pytest.mark.asyncio
class TestSplitMode:
    async def test_no_tools_moves_the_guidance_into_the_system_turn(self):
        agent, inner = _agent()

        await agent.invoke(_QUERY, chat_history=_HISTORY)

        system_content, user_content = _split_turns(inner)
        assert system_content == [
            {
                "type": "text",
                "text": create_tool_agent_no_tools_prompt(_BASE),
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": _SUFFIX},
        ]
        assert user_content.startswith(create_conversation_context(_HISTORY))
        assert f"User Query: {_QUERY}" in user_content

    async def test_tools_keep_the_descriptions_in_the_cached_block(self):
        tool = _weather_tool()
        agent, inner = _agent(tools=[tool])

        await agent.invoke(_QUERY, chat_history=_HISTORY)

        system_content, user_content = _split_turns(inner)
        assert system_content[0]["text"] == create_tool_agent_tools_available_prompt(
            _BASE, create_tool_descriptions([tool])
        )
        assert "TOOL CALL FORMAT" in system_content[0]["text"]
        assert tool.description in system_content[0]["text"]
        assert "TOOL CALL FORMAT" not in user_content

    async def test_volatile_tail_is_the_last_block(self):
        agent, inner = _agent(tools=[_weather_tool()])

        await agent.invoke(_QUERY)

        system_content, _ = _split_turns(inner)
        assert system_content[-1] == {"type": "text", "text": _SUFFIX}
        assert "Current time" not in system_content[0]["text"]

    async def test_blank_base_still_yields_a_non_blank_cached_block(self):
        agent, inner = _agent(tools=[_weather_tool()], system_prompt=_SUFFIX)

        await agent.invoke(_QUERY)

        system_content, _ = _split_turns(inner)
        assert system_content[0]["text"].strip()
        assert system_content[0]["cache_control"] == {"type": "ephemeral"}

    async def test_split_relocates_the_volatile_tail_and_loses_nothing(self):
        tool = _weather_tool()
        split_agent, split_inner = _agent(tools=[tool])
        fused_agent, fused_inner = _agent(tools=[tool], caching=False)

        await split_agent.invoke(_QUERY, chat_history=_HISTORY)
        await fused_agent.invoke(_QUERY, chat_history=_HISTORY)

        system_content, user_content = _split_turns(split_inner)
        split_text = "".join(block["text"] for block in system_content) + "\n\n" + user_content
        fused_text = _fused_text(fused_inner)

        assert split_text != fused_text
        assert split_text.replace(_SUFFIX, "", 1) == fused_text.replace(_SUFFIX, "", 1)


@pytest.mark.asyncio
class TestSplitModeStillDrivesTheWorkflow:
    async def test_json_tool_call_parses_from_a_split_mode_response(self):
        tool = _weather_tool()
        agent, _ = _agent(tools=[tool], replies=[_TOOL_CALL_JSON, _DIRECT_JSON])

        result = await agent.invoke(_QUERY)

        assert result["status"] == "success"
        assert result["tools_used"][0]["tool_name"] == "weather"
        assert result["tools_used"][0]["args"] == {"city": "Berlin"}
        tool.function.assert_awaited_once_with({"parameters": {"city": "Berlin"}})

    async def test_direct_response_parses_from_a_split_mode_response(self):
        agent, _ = _agent(tools=[_weather_tool()], replies=[_DIRECT_JSON])

        result = await agent.invoke(_QUERY)

        assert result["status"] == "success"
        assert result["response"] == "It is sunny."

    async def test_continuation_appends_to_the_user_turn_only(self):
        agent, inner = _agent(tools=[_weather_tool()], replies=[_TOOL_CALL_JSON, _DIRECT_JSON])

        await agent.invoke(_QUERY)

        first_system, first_user = inner.seen[0][0].content, inner.seen[0][1].content
        second_system, second_user = inner.seen[1][0].content, inner.seen[1][1].content
        assert second_system == first_system
        assert second_user.startswith(first_user)
        assert "Tool Result from weather" in second_user

    async def test_repeated_iterations_never_stack_markers(self):
        agent, inner = _agent(tools=[_weather_tool()], replies=[_TOOL_CALL_JSON, _DIRECT_JSON])

        await agent.invoke(_QUERY)

        assert len(inner.seen) == 2
        for sent in inner.seen:
            assert sum("cache_control" in block for block in sent[0].content) == 1

    async def test_no_tools_workflow_returns_the_direct_response(self):
        agent, _ = _agent(replies=[_DIRECT_JSON])

        result = await agent.invoke(_QUERY)

        assert result["response"] == "It is sunny."
        assert result["no_tools_available"] is True


@pytest.mark.asyncio
class TestUntouchedPaths:
    async def test_select_tool_still_sends_one_user_turn(self):
        agent, inner = _agent(tools=[_weather_tool()], replies=["use weather"])

        await agent.select_tool(_QUERY)

        sent = inner.seen[-1]
        assert len(sent) == 1
        assert isinstance(sent[0], HumanMessage)

    async def test_llm_failure_still_returns_an_error_response(self):
        agent, _ = _agent(tools=[_weather_tool()])
        agent.llm_model = MagicMock(ainvoke=AsyncMock(side_effect=RuntimeError("provider down")))

        result = await agent.invoke(_QUERY)

        assert result["status"] == "error"
        assert "provider down" in result["error"]
