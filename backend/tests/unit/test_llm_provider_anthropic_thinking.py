"""Anthropic request options build_chat_model derives from the provider form, and the
output floor a caller may ask for. Which parameters a Claude generation accepts is decided
in model_params.py and tested in test_llm_model_params.py."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.workflow.llm.provider import apply_max_tokens_floor, build_chat_model

_INIT = "langchain.chat_models.init_chat_model"


async def _kwargs(connection_data, model_name):
    with patch(_INIT) as init, patch.dict("os.environ"):
        init.return_value = MagicMock(name="inner-model")
        await build_chat_model("anthropic", connection_data, model_name)
    return init.call_args.kwargs


@pytest.mark.asyncio
class TestBuildChatModelThinking:
    async def test_a_new_model_gets_adaptive_thinking_and_no_sampling_setting(self):
        kwargs = await _kwargs(
            {"api_key": "k", "thinking_enabled": True, "thinking_budget_tokens": 4000, "temperature": 0.2},
            "claude-sonnet-5-5",
        )
        assert kwargs["thinking"] == {"type": "adaptive"}
        assert "temperature" not in kwargs
        assert "thinking_enabled" not in kwargs and "thinking_budget_tokens" not in kwargs

    async def test_an_older_model_keeps_the_budget_and_temperature_one(self):
        kwargs = await _kwargs(
            {"api_key": "k", "thinking_enabled": True, "thinking_budget_tokens": 4000, "temperature": 0.2},
            "claude-3-7-sonnet-20250219",
        )
        assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 4000}
        assert kwargs["temperature"] == 1

    async def test_thinking_off_sends_nothing_about_it(self):
        kwargs = await _kwargs({"api_key": "k", "thinking_enabled": False, "thinking_budget_tokens": 4000}, "claude-sonnet-5-5")
        assert "thinking" not in kwargs and "thinking_budget_tokens" not in kwargs


class TestMaxTokensFloor:
    def test_raises_a_lower_stored_value(self):
        assert apply_max_tokens_floor({"api_key": "k", "max_tokens": 1024}, 16000) == {"api_key": "k", "max_tokens": 16000}

    def test_keeps_a_higher_or_equal_stored_value(self):
        for stored in (16000, 32000, "20000"):
            data = {"max_tokens": stored}
            assert apply_max_tokens_floor(data, 16000) is data

    def test_a_form_without_the_setting_is_left_alone(self):
        data = {"api_key": "k"}
        assert apply_max_tokens_floor(data, 16000) is data

    def test_an_unreadable_stored_value_is_replaced(self):
        assert apply_max_tokens_floor({"max_tokens": "lots"}, 16000)["max_tokens"] == 16000

    def test_no_floor_changes_nothing(self):
        data = {"max_tokens": 1024}
        assert apply_max_tokens_floor(data, None) is data
        assert apply_max_tokens_floor(data, 0) is data

