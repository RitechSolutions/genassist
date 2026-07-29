"""Unit tests for ReActAgentLC token-usage capture"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.modules.workflow.agents.react_agent_lc import ReActAgentLC


def _build_agent(fake_result):
    with patch(
        "app.modules.workflow.agents.react_agent_lc.create_agent",
        return_value=MagicMock(),
    ):
        agent = ReActAgentLC(
            llm_model=MagicMock(),
            system_prompt="you are a helpful agent",
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
