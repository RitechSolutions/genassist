"""Anthropic request options build_chat_model derives from the provider form: the
thinking shape each Claude generation accepts, and the output floor a caller may ask for"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.workflow.llm.provider import (
    anthropic_thinking,
    apply_max_tokens_floor,
    build_chat_model,
    claude_version,
    without_rejected_sampling,
)

_INIT = "langchain.chat_models.init_chat_model"


async def _kwargs(connection_data, model_name):
    with patch(_INIT) as init, patch.dict("os.environ"):
        init.return_value = MagicMock(name="inner-model")
        await build_chat_model("anthropic", connection_data, model_name)
    return init.call_args.kwargs


class TestClaudeVersion:
    @pytest.mark.parametrize(
        ("model", "version"),
        [
            ("claude-sonnet-5-5", (5, 5)),
            ("claude-fable-5-1", (5, 1)),
            ("claude-opus-4-6", (4, 6)),
            ("claude-opus-4-1-20250805", (4, 1)),
            ("claude-sonnet-4-20250514", (4, 0)),
            ("claude-3-7-sonnet-20250219", (3, 7)),
            ("claude-3-5-haiku-20241022", (3, 5)),
            ("CLAUDE-HAIKU-4-5", (4, 5)),
            ("gpt-4o", None),
            ("", None),
            (None, None),
        ],
    )
    def test_reads_the_generation_out_of_the_model_id(self, model, version):
        assert claude_version(model) == version


class TestThinkingShape:
    def test_claude_4_6_and_later_think_adaptively(self):
        for model in ("claude-opus-4-6", "claude-sonnet-5-5", "claude-fable-5-1", "claude-opus-4-7"):
            assert anthropic_thinking(model, 2000) == {"type": "adaptive"}, model

    def test_older_models_keep_the_budget(self):
        for model in ("claude-3-7-sonnet-20250219", "claude-sonnet-4-5-20250929", "claude-opus-4-1"):
            assert anthropic_thinking(model, 2000) == {"type": "enabled", "budget_tokens": 2000}, model

    def test_an_unknown_id_keeps_the_budget_form(self):
        assert anthropic_thinking("my-fine-tune", 1500) == {"type": "enabled", "budget_tokens": 1500}


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


class TestSamplingSettings:
    """Claude 4.7+ answers temperature/top_p/top_k with 400 "`temperature` is deprecated for this model"."""

    def test_claude_4_7_and_later_drop_every_sampling_setting(self):
        for model in ("claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-5-5", "claude-fable-5-1", "claude-haiku-5-5"):
            data = {"api_key": "k", "temperature": 0.7, "top_p": 0.9, "top_k": 40, "max_tokens": 16000}
            assert without_rejected_sampling(data, model) == {"api_key": "k", "max_tokens": 16000}, model

    def test_older_models_keep_their_settings(self):
        for model in ("claude-opus-4-6", "claude-sonnet-4-5-20250929", "claude-3-7-sonnet-20250219", "my-fine-tune"):
            data = {"api_key": "k", "temperature": 0.7}
            assert without_rejected_sampling(data, model) is data, model

    @pytest.mark.asyncio
    async def test_build_chat_model_sends_no_temperature_to_a_new_model_with_thinking_off(self):
        kwargs = await _kwargs({"api_key": "k", "temperature": 0.7, "thinking_enabled": False}, "claude-sonnet-5-5")
        assert "temperature" not in kwargs and "top_p" not in kwargs and "top_k" not in kwargs
        assert kwargs["model"] == "claude-sonnet-5-5"

    @pytest.mark.asyncio
    async def test_build_chat_model_keeps_temperature_for_an_older_model(self):
        kwargs = await _kwargs({"api_key": "k", "temperature": 0.7}, "claude-sonnet-4-5-20250929")
        assert kwargs["temperature"] == 0.7
