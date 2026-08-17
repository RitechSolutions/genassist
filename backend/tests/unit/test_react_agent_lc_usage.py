"""Unit tests for ReActAgentLC token-usage capture"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.modules.workflow.agents.react_agent_lc import ReActAgentLC

_CREATE_AGENT = "app.modules.workflow.agents.react_agent_lc.create_agent"


def _build_agent(fake_result, system_prompt="you are a helpful agent"):
    with patch(_CREATE_AGENT, return_value=MagicMock()):
        agent = ReActAgentLC(
            llm_model=MagicMock(),
            system_prompt=system_prompt,
            tools=[],
        )
    agent.agent_executor.ainvoke = AsyncMock(return_value=fake_result)
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
