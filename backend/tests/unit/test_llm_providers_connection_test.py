"""Unit tests for LlmProviderService.test_connection"""

from typing import Any
from unittest.mock import AsyncMock, patch

import botocore.exceptions as botocore_exceptions
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.modules.workflow.llm.prompt_caching_chat_model import PromptCachingChatModel
from app.repositories.llm_providers import LlmProviderRepository
from app.services.app_settings import AppSettingsService
from app.services.llm_providers import LlmProviderService

_BUILD = "app.modules.workflow.llm.provider.build_chat_model"


class _CapturingModel(BaseChatModel):
    seen: list = []
    error: Any = None

    @property
    def _llm_type(self) -> str:
        return "capturing"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        raise NotImplementedError

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        if self.error is not None:
            raise self.error
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="pong"))])


@pytest.fixture
def service():
    return LlmProviderService(
        repository=AsyncMock(spec=LlmProviderRepository),
        app_settings_service=AsyncMock(spec=AppSettingsService),
    )


async def _test_connection(service, built_model, **connection_data):
    with patch(_BUILD, new=AsyncMock(return_value=built_model)):
        return await service.test_connection("bedrock", {"model": "a-model", **connection_data})


@pytest.mark.asyncio
class TestProbeShape:
    @pytest.mark.parametrize("cache_style", ["bedrock_converse", "anthropic", None], ids=repr)
    async def test_the_probe_is_a_plain_ping(self, service, cache_style):
        model = _CapturingModel()
        built = model if cache_style is None else PromptCachingChatModel(inner=model, cache_style=cache_style)
        result = await _test_connection(service, built)

        assert result == {"success": True, "message": "Connection successful."}
        assert [type(m) for m in model.seen[-1]] == [HumanMessage]
        assert model.seen[-1][0].content == "ping"


@pytest.mark.asyncio
class TestFailures:
    async def test_a_provider_error_reports_failure(self, service):
        inner = _CapturingModel(
            error=botocore_exceptions.ClientError(
                {
                    "Error": {"Code": "ValidationException", "Message": "model is not supported"},
                    "ResponseMetadata": {"HTTPStatusCode": 400},
                },
                "Converse",
            )
        )
        result = await _test_connection(service, PromptCachingChatModel(inner=inner, cache_style="bedrock_converse"))

        assert result["success"] is False
        assert "model is not supported" in result["message"]

    async def test_build_failure_reports_failure(self, service):
        with patch(_BUILD, new=AsyncMock(side_effect=ValueError("bad region"))):
            result = await service.test_connection("bedrock", {"model": "a-model"})

        assert result == {"success": False, "message": "bad region"}
