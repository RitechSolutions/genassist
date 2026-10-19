"""Editor builds get one attempt with a bounded wait, so one click is never two billed calls"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.workflow.llm.provider import build_chat_model

_INIT = "langchain.chat_models.init_chat_model"


async def _kwargs(provider, connection_data, call_timeout_seconds=None, model_name="a-model"):
    with patch(_INIT) as init, patch.dict("os.environ"):
        init.return_value = MagicMock(name="inner-model")
        await build_chat_model(provider, connection_data, model_name, call_timeout_seconds=call_timeout_seconds)
    return init.call_args.kwargs


@pytest.mark.asyncio
class TestSingleAttempt:
    @pytest.mark.parametrize(
        ("provider", "connection_data"),
        [
            ("openai", {"api_key": "k"}),
            ("vllm", {"base_url": "http://vllm:8000/v1"}),
            ("azure_openai", {"api_key": "k"}),
            ("anthropic", {"api_key": "k"}),
        ],
    )
    async def test_sdk_families_get_the_timeout_and_no_retries(self, provider, connection_data):
        kwargs = await _kwargs(provider, connection_data, 120)
        assert kwargs["timeout"] == 120
        assert kwargs["max_retries"] == 0

    async def test_gemini_counts_the_first_attempt_in_its_retries(self):
        kwargs = await _kwargs("google_genai", {"api_key": "k"}, 120)
        assert kwargs["timeout"] == 120
        assert kwargs["max_retries"] == 1

    async def test_bedrock_gets_a_botocore_config_with_one_attempt(self):
        kwargs = await _kwargs("bedrock", {"region_name": "eu-central-1"}, 120, "eu.amazon.nova-2-lite-v1:0")
        assert kwargs["config"].read_timeout == 120
        assert kwargs["config"].retries == {"total_max_attempts": 1}

    async def test_no_timeout_leaves_the_build_untouched(self):
        kwargs = await _kwargs("openai", {"api_key": "k", "timeout": 60, "max_retries": 3})
        assert kwargs["timeout"] == 60
        assert kwargs["max_retries"] == 3

    @pytest.mark.parametrize("provider", ["ollama", "mistralai"])
    async def test_a_family_without_a_spelling_is_untouched(self, provider):
        kwargs = await _kwargs(provider, {"base_url": "http://ollama:11434"}, 120)
        assert "timeout" not in kwargs
        assert "max_retries" not in kwargs
        assert "config" not in kwargs

    async def test_the_timeout_overrides_the_stored_form_values(self):
        kwargs = await _kwargs("openai", {"api_key": "k", "timeout": 60, "max_retries": 3}, 120)
        assert kwargs["timeout"] == 120
        assert kwargs["max_retries"] == 0
