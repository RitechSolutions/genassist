import pytest

from app.modules.workflow.llm.model_params import (
    claude_rejects_sampling,
    claude_uses_adaptive_thinking,
    deterministic_kwargs,
    openai_accepts_reasoning_none,
    openai_supports_reasoning_effort,
)
from app.modules.workflow.llm.provider import build_chat_model


class TestClaudeRules:
    @pytest.mark.parametrize(
        "model",
        [
            "claude-sonnet-5-5",
            "claude-opus-5",
            "claude-haiku-5-5",
            "claude-fable-5-1",
            "claude-opus-4-7",
            "claude-opus-4-8",
            "us.anthropic.claude-sonnet-5-5-v1:0",
            "anthropic/claude-sonnet-5.5",
        ],
    )
    def test_newer_models_reject_sampling(self, model):
        assert claude_rejects_sampling(model)

    @pytest.mark.parametrize(
        "model",
        [
            "claude-sonnet-4-6",
            "claude-opus-4-6",
            "claude-haiku-4-5",
            "claude-opus-4-20250514",
            "claude-3-sonnet-20240229",
            "gpt-4o",
            None,
        ],
    )
    def test_older_models_keep_sampling(self, model):
        assert not claude_rejects_sampling(model)

    @pytest.mark.parametrize("model", ["claude-sonnet-4-6", "claude-opus-4-7", "claude-sonnet-5-5"])
    def test_adaptive_thinking_from_4_6(self, model):
        assert claude_uses_adaptive_thinking(model)

    @pytest.mark.parametrize("model", ["claude-haiku-4-5", "claude-sonnet-4-20250514", "claude-3-opus-20240229"])
    def test_budget_thinking_before_4_6(self, model):
        assert not claude_uses_adaptive_thinking(model)


class TestOpenAIRules:
    @pytest.mark.parametrize("model", ["gpt-5", "gpt-5-mini", "gpt-5.1", "gpt-5.6-terra", "o1-mini", "o3"])
    def test_reasoning_models(self, model):
        assert openai_supports_reasoning_effort(model)

    @pytest.mark.parametrize("model", ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "gpt-5-chat-latest", "ft:gpt-4o-mini:org::abc"])
    def test_non_reasoning_models(self, model):
        assert not openai_supports_reasoning_effort(model)

    @pytest.mark.parametrize("model", ["gpt-5.1", "gpt-5.2", "gpt-5.6-terra", "openai/gpt-5.1"])
    def test_none_accepted_from_5_1(self, model):
        assert openai_accepts_reasoning_none(model)

    @pytest.mark.parametrize("model", ["gpt-5", "gpt-5-mini", "gpt-5.2-pro", "gpt-5.1-codex", "o3", "gpt-4o"])
    def test_none_not_accepted(self, model):
        assert not openai_accepts_reasoning_none(model)


class _FakeModel:
    def __init__(self, model):
        self.model = model


def test_deterministic_kwargs_skips_temperature_for_newer_claude():
    assert deterministic_kwargs(_FakeModel("claude-sonnet-5-5")) == {}
    assert deterministic_kwargs(_FakeModel("gpt-4o")) == {"temperature": 0}


@pytest.mark.asyncio
class TestBuildChatModelAnthropic:
    async def test_sonnet_5_5_sends_no_temperature(self):
        llm = await build_chat_model(
            "anthropic", {"api_key": "x", "temperature": 0.7, "max_tokens": 1024}, "claude-sonnet-5-5"
        )
        assert llm.temperature is None

    async def test_sonnet_5_5_thinking_is_adaptive_without_temperature(self):
        llm = await build_chat_model(
            "anthropic",
            {"api_key": "x", "temperature": 0.7, "thinking_enabled": True, "thinking_budget_tokens": 3000},
            "claude-sonnet-5-5",
        )
        assert llm.thinking == {"type": "adaptive"}
        assert llm.temperature is None

    async def test_older_claude_keeps_budget_thinking(self):
        llm = await build_chat_model(
            "anthropic",
            {"api_key": "x", "temperature": 0.7, "thinking_enabled": True, "thinking_budget_tokens": 3000},
            "claude-haiku-4-5",
        )
        assert llm.thinking == {"type": "enabled", "budget_tokens": 3000}
        assert llm.temperature == 1

    async def test_older_claude_keeps_temperature(self):
        llm = await build_chat_model("anthropic", {"api_key": "x", "temperature": 0.3}, "claude-sonnet-4-6")
        assert llm.temperature == 0.3

    async def test_cleared_temperature_is_left_out(self):
        llm = await build_chat_model("anthropic", {"api_key": "x", "temperature": None}, "claude-sonnet-4-6")
        assert llm.temperature is None


@pytest.mark.asyncio
class TestBuildChatModelOpenAIReasoning:
    async def test_none_is_sent_to_gpt_5_1_and_keeps_temperature(self):
        llm = await build_chat_model(
            "openai", {"api_key": "x", "temperature": 0.7, "reasoning_effort": "none"}, "gpt-5.6-terra"
        )
        assert llm.reasoning_effort == "none"
        assert llm.temperature == 0.7

    async def test_none_is_left_out_for_gpt_4o(self):
        llm = await build_chat_model("openai", {"api_key": "x", "reasoning_effort": "none"}, "gpt-4o")
        assert llm.reasoning_effort is None

    async def test_effort_is_left_out_for_non_reasoning_model(self):
        llm = await build_chat_model("openai", {"api_key": "x", "reasoning_effort": "high"}, "gpt-4o")
        assert llm.reasoning_effort is None

    async def test_effort_is_sent_to_reasoning_model(self):
        llm = await build_chat_model("openai", {"api_key": "x", "reasoning_effort": "high"}, "gpt-5")
        assert llm.reasoning_effort == "high"

    async def test_none_is_left_out_for_original_gpt_5(self):
        llm = await build_chat_model("openai", {"api_key": "x", "reasoning_effort": "none"}, "gpt-5")
        assert llm.reasoning_effort is None
