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
class TestBedrockFamilyGuard:

    @pytest.mark.parametrize(
        "model_name",
        [
            "eu.amazon.nova-2-lite-v1:0",
            "eu.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.anthropic.claude-sonnet-4-5-v1:0",
        ],
    )
    async def test_cacheable_families_wrap(self, model_name):
        llm, _ = await _build("bedrock", {"prompt_caching_enabled": True}, model_name)
        assert isinstance(llm, PromptCachingChatModel)

    @pytest.mark.parametrize(
        "model_name",
        [
            "meta.llama3-3-70b-instruct-v1:0",
            "mistral.mistral-large-2407-v1:0",
            "amazon.titan-text-premier-v1:0",
            "deepseek.r1-v1:0",
        ],
    )
    async def test_families_without_cache_support_run_uncached(self, model_name):
        llm, init = await _build("bedrock", {"prompt_caching_enabled": True}, model_name)
        assert llm is init.return_value, "wrapping these fails every call with a ValidationException"

    async def test_arn_wraps_on_the_selected_model_provider(self):
        llm, _ = await _build(
            "bedrock",
            {"prompt_caching_enabled": True, "model_provider": "anthropic"},
            "arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/abc123",
        )
        assert isinstance(llm, PromptCachingChatModel)

    async def test_arn_wraps_on_a_family_it_names_itself(self):
        llm, _ = await _build(
            "bedrock",
            {"prompt_caching_enabled": True, "model_provider": "amazon"},
            "arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-2-lite-v1:0",
        )
        assert isinstance(llm, PromptCachingChatModel)

    async def test_family_less_arn_under_amazon_stays_uncached(self):
        llm, init = await _build(
            "bedrock",
            {"prompt_caching_enabled": True, "model_provider": "amazon"},
            "arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/abc123",
        )
        assert llm is init.return_value

    async def test_missing_model_name_stays_uncached(self):
        llm, init = await _build("bedrock", {"prompt_caching_enabled": True}, None)
        assert llm is init.return_value

    async def test_anthropic_direct_is_unaffected_by_the_model_name(self):
        llm, _ = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": True}, "some-model")
        assert isinstance(llm, PromptCachingChatModel)


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
