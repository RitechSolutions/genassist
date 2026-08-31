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
    create_tool_agent_no_tools_query_portion,
    create_tool_agent_no_tools_query_prompt,
    create_tool_agent_tools_available_prompt,
    create_tool_agent_tools_query_portion,
    create_tool_agent_tools_query_prompt,
)
from app.modules.workflow.agents.agent_utils import create_tool_descriptions
from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.agents.tool_agent import ToolAgent
from app.modules.workflow.llm.fallback_chat_model import FallbackChatModel
from app.modules.workflow.llm.prompt_caching_chat_model import (
    PROMPT_CACHE_OPT_IN_KEY,
    PromptCachingChatModel,
)

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


_PARTS = (_BASE, _SUFFIX)


def _agent(*, tools=None, replies=None, caching=True, parts=_PARTS, system_prompt=None, stable_tool_names=None):
    inner = _CapturingModel(replies=replies or [_DIRECT_JSON])
    llm = PromptCachingChatModel(inner=inner, cache_style="anthropic") if caching else inner
    agent = ToolAgent(
        llm_model=llm,
        system_prompt=_BASE + _SUFFIX if system_prompt is None else system_prompt,
        tools=tools if tools is not None else [],
        stable_volatile_parts=parts,
        stable_tool_names=stable_tool_names,
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
            ({"parts": None}, False),
        ],
        ids=["caching_and_parts", "no_caching", "no_parts"],
    )
    def test_split_only_when_the_prompt_is_marked_cacheable(self, kwargs, expected):
        agent, _ = _agent(**kwargs)

        assert agent._cache_split is expected

    def test_a_mixed_fallback_chain_stays_fused(self):
        chain = FallbackChatModel(
            models=[
                _CapturingModel(replies=[_DIRECT_JSON]),
                PromptCachingChatModel(inner=_CapturingModel(replies=[_DIRECT_JSON]), cache_style="anthropic"),
            ]
        )
        agent = ToolAgent(llm_model=chain, system_prompt=_BASE + _SUFFIX, tools=[], stable_volatile_parts=_PARTS)

        assert agent._cache_split is False
        assert agent.cache_split_decision == (False, "mixed_fallback_chain")

    @pytest.mark.parametrize(
        "kwargs,expected",
        [
            ({}, (True, None)),
            ({"caching": False}, (False, "unsupported_cache_markers")),
            ({"parts": None}, (False, "volatile_prompt")),
        ],
        ids=["caching_and_parts", "no_caching", "no_parts"],
    )
    def test_the_stored_decision_names_the_gate(self, kwargs, expected):
        agent, _ = _agent(**kwargs)

        assert agent.cache_split_decision == expected

    def test_a_blank_base_is_still_eligible_through_the_enhanced_prefix(self):
        agent, _ = _agent(tools=[_weather_tool()], system_prompt=_SUFFIX, parts=("", _SUFFIX))

        assert agent.cache_split_decision == (True, None)

    def test_construction_never_builds_the_enhanced_prompt(self, monkeypatch):
        def _boom(self, base_prompt=None):
            raise AssertionError("the enhanced prompt must stay invocation-local")

        monkeypatch.setattr(ToolAgent, "_create_enhanced_system_prompt", _boom)

        for kwargs in ({}, {"caching": False}, {"parts": None}):
            agent, _ = _agent(tools=[_weather_tool()], **kwargs)
            assert isinstance(agent.cache_split_decision, tuple)


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

    async def test_caching_model_without_parts_stays_fused_and_unmarked(self):
        agent, inner = _agent(tools=[_weather_tool()], parts=None)

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

    async def test_the_system_turn_carries_the_opt_in_tag(self):
        agent, inner = _agent(tools=[_weather_tool()])

        await agent.invoke(_QUERY)

        assert inner.seen[-1][0].additional_kwargs == {PROMPT_CACHE_OPT_IN_KEY: True}

    async def test_tools_added_after_construction_reach_the_cached_block(self):
        agent, inner = _agent(tools=[_weather_tool()])
        late = _weather_tool()
        late.name = "currency"
        late.description = "Convert between currencies."
        agent.add_tool(late)

        await agent.invoke(_QUERY)

        system_content, _ = _split_turns(inner)
        assert late.description in system_content[0]["text"]

    async def test_blank_base_still_yields_a_non_blank_cached_block(self):
        agent, inner = _agent(tools=[_weather_tool()], system_prompt=_SUFFIX, parts=("", _SUFFIX))

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


def _delegation_tool(name="delegate_to_helper"):
    return BaseTool(
        node_id="child-1",
        name=name,
        description=f"Delegate a task to the '{name}' sub-agent (single_turn mode).",
        parameters={"task": {"type": "string", "description": "The task.", "required": True}},
        function=AsyncMock(return_value="{}"),
        return_direct=True,
    )


def _return_direct_tool(name="lookup_order"):
    tool = _weather_tool("record 42")
    tool.name = name
    tool.description = "Look up an order and return it verbatim."
    tool.return_direct = True
    return tool


async def _cached_head(tools, stable_tool_names, parts=_PARTS, system_prompt=None):
    agent, inner = _agent(
        tools=tools, stable_tool_names=stable_tool_names, parts=parts, system_prompt=system_prompt
    )
    await agent.invoke(_QUERY)
    system_content, _ = _split_turns(inner)
    return system_content


_STABLE_NAMES = frozenset({"weather"})


@pytest.mark.asyncio
class TestDelegationToolsSitPastTheMarker:

    async def test_the_cached_block_excludes_non_stable_descriptions(self):
        weather, delegate = _weather_tool(), _delegation_tool()
        system_content = await _cached_head([weather, delegate], _STABLE_NAMES)

        assert weather.description in system_content[0]["text"]
        assert delegate.description not in system_content[0]["text"]
        assert delegate.description in system_content[-1]["text"]

    async def test_the_relocation_loses_nothing(self):
        weather, delegate = _weather_tool(), _delegation_tool()
        system_content = await _cached_head([weather, delegate], _STABLE_NAMES)

        joined = "".join(block["text"] for block in system_content)
        expected = create_tool_agent_tools_available_prompt(
            _BASE, create_tool_descriptions([weather, delegate])
        )
        assert joined == expected + _SUFFIX

    async def test_the_cached_block_is_identical_across_every_drop(self):
        weather = _weather_tool()
        turns = [
            [weather, _delegation_tool("delegate_to_a"), _delegation_tool("delegate_to_b")],
            [weather, _delegation_tool("delegate_to_b")],
            [weather],
        ]

        heads = [(await _cached_head(tools, _STABLE_NAMES))[0] for tools in turns]

        assert heads[0] == heads[1] == heads[2]

    async def test_a_non_stable_tool_surviving_the_drops_stays_past_the_marker(self):
        weather, finish = _weather_tool(), _delegation_tool("finish_task")
        with_delegate = await _cached_head([weather, _delegation_tool(), finish], _STABLE_NAMES)
        final_turn = await _cached_head([weather, finish], _STABLE_NAMES)

        assert with_delegate[0] == final_turn[0]
        assert finish.description in final_turn[-1]["text"]

    async def test_a_return_direct_tool_outside_a_delegation_run_stays_cached(self):
        lookup, weather = _return_direct_tool(), _weather_tool()
        system_content = await _cached_head([lookup, weather], None)

        assert system_content[0]["text"] == create_tool_agent_tools_available_prompt(
            _BASE, create_tool_descriptions([lookup, weather])
        )
        assert system_content[0]["cache_control"] == {"type": "ephemeral"}

    async def test_an_all_delegation_toolset_caches_exactly_the_header(self):
        heads = [
            (
                await _cached_head(
                    tools, frozenset(), parts=("", _SUFFIX), system_prompt=_SUFFIX
                )
            )[0]
            for tools in ([_delegation_tool("delegate_to_a"), _delegation_tool("delegate_to_b")],
                          [_delegation_tool("delegate_to_b")])
        ]

        assert heads[0] == heads[1]
        assert heads[0]["text"] == "\n\nAVAILABLE TOOLS:\n"
        assert heads[0]["cache_control"] == {"type": "ephemeral"}


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

    async def test_the_system_turn_is_built_once_per_invoke(self):
        agent, inner = _agent(tools=[_weather_tool()], replies=[_TOOL_CALL_JSON, _DIRECT_JSON])
        agent._cacheable_system_message = MagicMock(side_effect=agent._cacheable_system_message)

        await agent.invoke(_QUERY)

        assert len(inner.seen) == 2
        agent._cacheable_system_message.assert_called_once()

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


_NO_TOOLS_PORTION = """CTX

User Query: Q

Since no tools are available, provide a direct response based on your knowledge using the JSON format specified above."""

_TOOLS_PORTION = """CTX

User Query: Q

Analyze the query and decide if you need to use any tools. Respond using the JSON format specified above.
- If you need a tool, use the "tool_call" action format
- If you can answer directly, use the "direct_response" action format
- Make sure to include all required parameters and follow the parameter types specified
- Always include your reasoning for the decision"""

_PORTION_CASES = [
    pytest.param(
        create_tool_agent_no_tools_query_prompt,
        create_tool_agent_no_tools_query_portion,
        _NO_TOOLS_PORTION,
        id="no_tools",
    ),
    pytest.param(
        create_tool_agent_tools_query_prompt,
        create_tool_agent_tools_query_portion,
        _TOOLS_PORTION,
        id="tools",
    ),
]


@pytest.mark.parametrize("fused,portion,expected", _PORTION_CASES)
class TestQueryPortions:
    def test_portion_renders_verbatim(self, fused, portion, expected):
        assert portion("CTX", "Q") == expected

    def test_fused_prompt_is_the_system_prompt_plus_the_portion(self, fused, portion, expected):
        assert fused("SYS", "CTX", "Q") == "SYS\n\n" + expected

    @pytest.mark.parametrize("system_prompt", ["", "SYS", "multi\nline", "{braces}", "trailing\n\n"], ids=repr)
    def test_portion_carries_no_part_of_the_system_prompt(self, fused, portion, expected, system_prompt):
        assert fused(system_prompt, "CTX", "Q") == system_prompt + "\n\n" + portion("CTX", "Q")
