"""Unit tests for the prompt-caching opt-in in build_chat_model"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config.settings import settings
from app.modules.workflow.llm.prompt_caching_chat_model import PromptCachingChatModel
from app.modules.workflow.llm.provider import build_chat_model

_INIT = "langchain.chat_models.init_chat_model"
_OPIK = "app.modules.workflow.llm.opik_tracing.get_opik_callbacks"


@pytest.fixture(autouse=True)
def _platform_flag_on(monkeypatch):
    monkeypatch.setattr(settings, "PROMPT_CACHING_FEATURE_ENABLED", True)


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
            "global.anthropic.claude-sonnet-5",
            "us.anthropic.claude-fable-5",
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

    @pytest.mark.parametrize(
        "model_name",
        [
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-opus-20240229-v1:0",
            "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
        ],
    )
    async def test_non_cacheable_claude_versions_run_uncached(self, model_name):
        llm, init = await _build("bedrock", {"prompt_caching_enabled": True}, model_name)
        assert llm is init.return_value, "wrapping these fails every call with a ValidationException"

    @pytest.mark.parametrize(
        "model_name",
        [
            "arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-2-lite-v1:0",
            "arn:aws:bedrock:us-east-1::inference-profile/us.anthropic.claude-sonnet-4-5-v1:0",
            "arn:aws:bedrock:us-east-1::inference-profile/global.anthropic.claude-fable-5",
        ],
    )
    async def test_arn_wraps_on_a_model_it_names_itself(self, model_name):
        llm, _ = await _build("bedrock", {"prompt_caching_enabled": True, "model_provider": "amazon"}, model_name)
        assert isinstance(llm, PromptCachingChatModel)

    @pytest.mark.parametrize("model_provider", ["anthropic", "amazon"])
    async def test_opaque_arns_stay_uncached(self, model_provider):
        llm, init = await _build(
            "bedrock",
            {"prompt_caching_enabled": True, "model_provider": model_provider},
            "arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/abc123",
        )
        assert llm is init.return_value

    @pytest.mark.parametrize(
        "model_name",
        [
            "arn:aws:bedrock:us-east-1:123456789012:custom-model/my-nova-finetune",
            "arn:aws:bedrock:us-east-1:123456789012:provisioned-model/nova-throughput",
            "arn:aws:bedrock:us-east-1:123456789012:custom-model/claude-sonnet-5-finetune",
            "arn:aws:bedrock:eu-central-1:123456789012:provisioned-model/claude-fable-5-throughput",
        ],
    )
    async def test_a_deployment_arn_never_inherits_its_base_family(self, model_name):
        llm, init = await _build("bedrock", {"prompt_caching_enabled": True, "model_provider": "amazon"}, model_name)
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
class TestPlatformWithhold:

    @pytest.fixture(autouse=True)
    def _flag_off(self, monkeypatch):
        monkeypatch.setattr(settings, "PROMPT_CACHING_FEATURE_ENABLED", False)

    async def test_a_stored_opt_in_stays_inert(self):
        llm, init = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": True})
        assert llm is init.return_value
        assert "prompt_caching_enabled" not in init.call_args.kwargs

    async def test_a_supported_bedrock_model_is_withheld_too(self):
        llm, init = await _build("bedrock", {"prompt_caching_enabled": True}, "us.amazon.nova-2-lite-v1:0")
        assert llm is init.return_value

    async def test_the_stored_connection_data_is_never_rewritten(self):
        connection_data = {"api_key": "k", "prompt_caching_enabled": True}
        await _build("anthropic", connection_data)
        assert connection_data == {"api_key": "k", "prompt_caching_enabled": True}


@pytest.mark.asyncio
class TestOpikCallbacks:
    async def test_callbacks_stay_on_the_inner_model(self):
        callback = MagicMock(name="opik-tracer")
        with patch(_OPIK, return_value=[callback]):
            llm, init = await _build("anthropic", {"api_key": "k", "prompt_caching_enabled": True})
        assert init.call_args.kwargs["callbacks"] == [callback]
        assert llm.callbacks is None
