from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.utils.encryption_utils import encrypt_key
from app.modules.workflow.llm.provider import LLMProvider, build_chat_model

_BEDROCK_KEYS = {"region_name": "eu-central-1", "aws_access_key_id": "x", "aws_secret_access_key": "y"}
_KEY_ID, _SECRET = "AKIAFAKEEXAMPLE00000", "fakeSecretExample"


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


@pytest.mark.asyncio
class TestStoredAwsKeys:
    @pytest.mark.parametrize("store", [encrypt_key, str], ids=["encrypted", "legacy-plaintext"])
    async def test_the_model_gets_the_plaintext_keys(self, store):
        row = SimpleNamespace(
            id="p1",
            llm_model_provider="bedrock",
            llm_model="eu.amazon.nova-2-lite-v1:0",
            connection_data={
                "region_name": "eu-central-1",
                "aws_access_key_id": store(_KEY_ID),
                "aws_secret_access_key": store(_SECRET),
            },
        )
        stored = dict(row.connection_data)
        injector = MagicMock()
        injector.get.return_value = AsyncMock()
        with (
            patch("app.dependencies.injector.injector", injector),
            patch("app.core.data_residency.assert_provider_residency", AsyncMock()),
            patch("app.core.utils.db_connection_utils.release_idle_connection", AsyncMock()),
        ):
            llm = await LLMProvider().get_model_from_provider(row)
        assert llm.aws_access_key_id.get_secret_value() == _KEY_ID
        assert llm.aws_secret_access_key.get_secret_value() == _SECRET
        assert row.connection_data == stored
