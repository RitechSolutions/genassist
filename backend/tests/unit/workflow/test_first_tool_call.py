"""The agent calls the chosen tool before answering each message"""

from types import SimpleNamespace
from typing import Any, List, Optional

import pytest
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import StructuredTool
from pydantic import Field

from app.modules.workflow.agents.first_tool_call import FirstToolCallMiddleware, model_can_be_told_which_tool

KNOWLEDGE_TOOL = "knowledge_base"
USER_MESSAGE = "and how long is the code good for?"


class ScriptedChatModel(BaseChatModel):
    """Answers with prepared replies and records the tool choice of every call"""

    replies: List[AIMessage] = Field(default_factory=list)
    tool_choices: List[Any] = Field(default_factory=list)
    supports_tool_choice_values: Optional[tuple] = None
    rejects_named_tool: bool = False

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, tool_choice=None, **kwargs):
        self.tool_choices.append(tool_choice)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        told_which_tool = bool(self.tool_choices and self.tool_choices[-1])
        if self.rejects_named_tool and told_which_tool:
            raise ValueError("400: tool_choice forcing tool use is not supported")
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def _tool_call(name: str, args: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}", "type": "tool_call"}])


def _recording_tool(name: str, calls: list) -> StructuredTool:
    async def search(query: str) -> str:
        calls.append(query)
        return "The unlock code is valid for 95 seconds."

    return StructuredTool.from_function(coroutine=search, name=name, description=f"{name} tool")


def _two_input_tool(calls: list) -> StructuredTool:
    async def lookup(order_id: str, email: str) -> str:
        calls.append((order_id, email))
        return "found"

    return StructuredTool.from_function(coroutine=lookup, name=KNOWLEDGE_TOOL, description="needs two inputs")


async def _run(model: ScriptedChatModel, tools: list, history: Optional[list] = None) -> list:
    agent = create_agent(model=model, tools=tools, middleware=[FirstToolCallMiddleware(KNOWLEDGE_TOOL)])
    result = await agent.ainvoke({"messages": [*(history or []), HumanMessage(content=USER_MESSAGE)]})
    return result["messages"]


@pytest.mark.asyncio
async def test_the_model_is_told_to_call_the_tool_first_and_writes_its_input():
    searches = []
    model = ScriptedChatModel(replies=[
        _tool_call(KNOWLEDGE_TOOL, {"query": "unlock code validity"}),
        AIMessage(content="It is valid for 95 seconds."),
    ])

    messages = await _run(model, [_recording_tool(KNOWLEDGE_TOOL, searches)])

    assert model.tool_choices == [KNOWLEDGE_TOOL, None]
    assert searches == ["unlock code validity"]
    assert messages[-1].content == "It is valid for 95 seconds."


@pytest.mark.asyncio
async def test_only_the_first_move_of_the_latest_message_is_forced():
    searches = []
    earlier_turn = [HumanMessage(content="How do I unlock a bike?"), AIMessage(content="Scan the code on the bike.")]
    model = ScriptedChatModel(replies=[
        _tool_call(KNOWLEDGE_TOOL, {"query": "unlock code validity"}),
        AIMessage(content="It is valid for 95 seconds."),
    ])

    await _run(model, [_recording_tool(KNOWLEDGE_TOOL, searches)], history=earlier_turn)

    assert model.tool_choices == [KNOWLEDGE_TOOL, None]
    assert len(searches) == 1


@pytest.mark.asyncio
async def test_a_model_that_ignores_the_instruction_gets_the_tool_called_with_the_user_message():
    searches = []
    model = ScriptedChatModel(replies=[
        AIMessage(content="I think it is about a minute."),
        AIMessage(content="It is valid for 95 seconds."),
    ])

    messages = await _run(model, [_recording_tool(KNOWLEDGE_TOOL, searches)])

    assert searches == [USER_MESSAGE]
    assert messages[-1].content == "It is valid for 95 seconds."
    assert not any(m.content == "I think it is about a minute." for m in messages)


@pytest.mark.asyncio
async def test_a_model_that_cannot_be_told_gets_the_tool_called_without_an_extra_model_call():
    searches = []
    model = ScriptedChatModel(
        replies=[AIMessage(content="It is valid for 95 seconds.")],
        supports_tool_choice_values=("auto", "any"),
    )

    messages = await _run(model, [_recording_tool(KNOWLEDGE_TOOL, searches)])

    assert searches == [USER_MESSAGE]
    assert model.tool_choices == [None]
    assert any(isinstance(m, ToolMessage) for m in messages)
    assert messages[-1].content == "It is valid for 95 seconds."


@pytest.mark.asyncio
async def test_a_provider_that_rejects_the_instruction_gets_the_tool_called_and_the_agent_answers():
    searches = []
    model = ScriptedChatModel(replies=[AIMessage(content="It is valid for 95 seconds.")], rejects_named_tool=True)

    messages = await _run(model, [_recording_tool(KNOWLEDGE_TOOL, searches)])

    assert model.tool_choices == [KNOWLEDGE_TOOL, None]
    assert searches == [USER_MESSAGE]
    assert messages[-1].content == "It is valid for 95 seconds."


@pytest.mark.asyncio
async def test_a_tool_with_several_inputs_is_not_called_with_the_user_message():
    calls = []
    model = ScriptedChatModel(replies=[AIMessage(content="Please give me your order number.")])

    messages = await _run(model, [_two_input_tool(calls)])

    assert calls == []
    assert messages[-1].content == "Please give me your order number."


@pytest.mark.asyncio
async def test_nothing_is_forced_when_the_tool_is_not_offered():
    model = ScriptedChatModel(replies=[AIMessage(content="Hello.")])

    messages = await _run(model, [_recording_tool("save_city", [])])

    assert model.tool_choices == [None]
    assert messages[-1].content == "Hello."


@pytest.mark.parametrize(
    ("choices", "expected"),
    [(None, True), (("auto", "any", "tool"), True), (("auto", "any"), False), ((), False)],
    ids=["not stated", "named tool supported", "named tool missing", "no tool choice"],
)
def test_whether_a_model_can_be_told_which_tool(choices, expected):
    assert model_can_be_told_which_tool(SimpleNamespace(supports_tool_choice_values=choices)) is expected


def test_a_fallback_chain_can_be_told_only_when_every_model_can():
    capable = SimpleNamespace(supports_tool_choice_values=("auto", "any", "tool"))
    unable = SimpleNamespace(supports_tool_choice_values=("auto",))

    assert model_can_be_told_which_tool(SimpleNamespace(models=[capable, capable])) is True
    assert model_can_be_told_which_tool(SimpleNamespace(models=[capable, unable])) is False


@pytest.mark.parametrize(
    ("thinking", "expected"),
    [({"type": "enabled", "budget_tokens": 2000}, False), ({"type": "adaptive"}, False), ({"type": "disabled"}, True), (None, True)],
    ids=["thinking on", "adaptive thinking", "thinking off", "no thinking setting"],
)
def test_an_anthropic_model_with_thinking_on_cannot_be_told(thinking, expected):
    assert model_can_be_told_which_tool(SimpleNamespace(thinking=thinking)) is expected


def test_the_model_inside_a_prompt_caching_wrapper_is_the_one_checked():
    thinking_model = SimpleNamespace(thinking={"type": "enabled"})
    unable = SimpleNamespace(supports_tool_choice_values=("auto",))

    assert model_can_be_told_which_tool(SimpleNamespace(inner=thinking_model)) is False
    assert model_can_be_told_which_tool(SimpleNamespace(models=[SimpleNamespace(inner=unable)])) is False
    assert model_can_be_told_which_tool(SimpleNamespace(inner=SimpleNamespace())) is True
