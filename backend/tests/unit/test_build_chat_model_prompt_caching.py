"""Unit tests for the prompt-caching opt-in in build_chat_model"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.workflow.llm.prompt_caching_chat_model import PromptCachingChatModel
from app.modules.workflow.llm.provider import build_chat_model

_INIT = "langchain.chat_models.init_chat_model"
_OPIK = "app.modules.workflow.llm.opik_tracing.get_opik_callbacks"


async def _build(provider, connection_data, model_name="a-model"):
    with patch(_INIT) as init:
        init.return_value = MagicMock(name="inner-model")
        llm = await build_chat_model(provider, connection_data, model_name)
    return llm, init


@pytest.mark.asyncio
class TestWrappedProviders:
    async def test_anthropic_flag_wraps_with_anthropic_style(self):
        llm, init = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": True})
        assert isinstance(llm, PromptCachingChatModel)
        assert llm.cache_style == "anthropic"
        assert llm.inner is init.return_value
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    async def test_bedrock_flag_wraps_with_bedrock_converse_style(self):
        llm, init = await _build(
            "bedrock",
            {"region_name": "eu-central-1", "prompt_caching_enabled": True},
            "eu.anthropic.claude-sonnet-4-5-v1:0",
        )
        assert isinstance(llm, PromptCachingChatModel)
        assert llm.cache_style == "bedrock_converse"
        assert init.call_args.kwargs["model_provider"] == "bedrock_converse"
        assert "prompt_caching_enabled" not in init.call_args.kwargs


@pytest.mark.asyncio
class TestUnwrappedCases:
    async def test_openai_stale_flag_is_stripped_without_wrapping(self):
        llm, init = await _build("openai", {"api_key": "k", "prompt_caching_enabled": True})
        assert llm is init.return_value
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    @pytest.mark.parametrize("raw", ["true", "false", "True", 1, 0, None, ""], ids=repr)
    async def test_only_a_real_true_enables_caching(self, raw):
        llm, init = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": raw})
        assert llm is init.return_value
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    async def test_no_flag_returns_the_plain_model(self):
        llm, init = await _build("anthropic", {"api_key": "k"})
        assert llm is init.return_value


@pytest.mark.asyncio
class TestOpikCallbacks:
    async def test_callbacks_stay_on_the_inner_model(self):
        callback = MagicMock(name="opik-tracer")
        with patch(_OPIK, return_value=[callback]):
            llm, init = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": True})
        assert init.call_args.kwargs["callbacks"] == [callback]
        assert llm.callbacks is None
