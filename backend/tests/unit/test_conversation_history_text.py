"""Stored agent turns reach the model as their reply only, in every history format"""

from unittest.mock import patch

import pytest

from app.modules.workflow.agents.memory import InMemoryConversationMemory, Message, history_text

_AGENT_TURN = {
    "message": "I built a support agent with a Zendesk tool.",
    "steps": [{"tool_name": "apply_plan", "tool_args": {"operations": "[" + "x" * 5000 + "]"}}],
    "tools_used": [{"tool_name": "apply_plan"}],
}


def test_history_text_keeps_only_the_reply_of_an_agent_turn():
    assert history_text(_AGENT_TURN) == "I built a support agent with a Zendesk tool."
    assert history_text({"message": "m", "tools_used": []}) == "m"


@pytest.mark.parametrize("content", ["plain text", {"message": "no steps here"}, {"result": 3}, ["a"], None, 7])
def test_history_text_leaves_everything_else_unchanged(content):
    assert history_text(content) is content


def _memory():
    memory = InMemoryConversationMemory("t")
    memory.messages = [Message("user", "Build a support agent"), Message("assistant", _AGENT_TURN)]
    return memory


@pytest.mark.asyncio
async def test_string_history_shows_the_reply_not_the_steps():
    text = await _memory().get_chat_history(as_string=True, max_messages=10)

    assert text == "User: Build a support agent\nAssistant: I built a support agent with a Zendesk tool."


@pytest.mark.asyncio
async def test_token_budget_counts_and_renders_the_reply_only():
    class _Counter:
        def count_tokens(self, text):
            return len(text)

    with patch("app.core.utils.token_utils.get_token_counter", return_value=_Counter()):
        # Both messages fit once the steps are not counted (they alone are 5,000+ characters).
        text = await _memory().get_chat_history_within_tokens(200, "openai", "gpt-4o", as_string=True)

    assert text == "User: Build a support agent\nAssistant: I built a support agent with a Zendesk tool."


@pytest.mark.asyncio
async def test_the_stored_message_itself_is_not_rewritten():
    memory = _memory()
    await memory.get_chat_history(as_string=True)

    assert memory.messages[1].content == _AGENT_TURN
    assert (await memory.get_messages())[1]["content"] == _AGENT_TURN
