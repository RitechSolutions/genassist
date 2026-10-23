import pytest

from app.modules.workflow.llm.provider import build_chat_model

_BEDROCK_KEYS = {"region_name": "eu-central-1", "aws_access_key_id": "x", "aws_secret_access_key": "y"}


@pytest.mark.asyncio
class TestBedrockStreaming:
    @pytest.mark.parametrize("model", ["eu.amazon.nova-2-lite-v1:0", "amazon.nova-2-lite-v1:0"])
    async def test_nova_2_lite_streams(self, model):
        llm = await build_chat_model("bedrock", _BEDROCK_KEYS, model)
        assert llm.disable_streaming is False

    @pytest.mark.parametrize("model", ["meta.llama3-1-70b-instruct-v1:0", "amazon.titan-text-express-v1"])
    async def test_other_bedrock_models_keep_the_library_default(self, model):
        llm = await build_chat_model("bedrock", _BEDROCK_KEYS, model)
        assert llm.disable_streaming == "tool_calling"


@pytest.mark.asyncio
class TestBedrockReadTimeout:
    @pytest.mark.parametrize("model", ["eu.amazon.nova-2-lite-v1:0", "eu.anthropic.claude-sonnet-4-5-v1:0"])
    async def test_runtime_client_waits_five_minutes_for_a_reply(self, model):
        llm = await build_chat_model("bedrock", _BEDROCK_KEYS, model)
        assert llm.client.meta.config.read_timeout == 300
        assert llm.client.meta.config.connect_timeout == 60
