"""Unit tests for LlmProviderService.test_connection"""

from typing import Any
from unittest.mock import AsyncMock, patch

import botocore.exceptions as botocore_exceptions
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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


def _system_content(sent: list):
    return [m for m in sent if isinstance(m, SystemMessage)][0].content


@pytest.mark.asyncio
class TestProbeShape:
    async def test_bedrock_cache_point_round_trips_to_the_provider(self, service):
        inner = _CapturingModel()
        result = await _test_connection(service, PromptCachingChatModel(inner=inner, cache_style="bedrock_converse"))

        assert result == {"success": True, "message": "Connection successful."}
        assert _system_content(inner.seen[-1]) == [
            {"type": "text", "text": "Connection test."},
            {"cachePoint": {"type": "default"}},
        ]
        assert inner.seen[-1][-1].content == "ping"

    async def test_anthropic_cache_control_round_trips_to_the_provider(self, service):
        inner = _CapturingModel()
        await _test_connection(service, PromptCachingChatModel(inner=inner, cache_style="anthropic"))

        assert _system_content(inner.seen[-1]) == [
            {"type": "text", "text": "Connection test.", "cache_control": {"type": "ephemeral"}}
        ]

    async def test_plain_ping_when_the_model_does_not_cache(self, service):
        model = _CapturingModel()
        result = await _test_connection(service, model)

        assert result["success"] is True
        assert [type(m) for m in model.seen[-1]] == [HumanMessage]
        assert model.seen[-1][0].content == "ping"


@pytest.mark.asyncio
class TestFailures:
    async def test_rejected_cache_point_reports_failure(self, service):
        inner = _CapturingModel(
            error=botocore_exceptions.ClientError(
                {
                    "Error": {"Code": "ValidationException", "Message": "cachePoint not supported"},
                    "ResponseMetadata": {"HTTPStatusCode": 400},
                },
                "Converse",
            )
        )
        result = await _test_connection(service, PromptCachingChatModel(inner=inner, cache_style="bedrock_converse"))

        assert result["success"] is False
        assert "cachePoint not supported" in result["message"]

    async def test_build_failure_reports_failure(self, service):
        with patch(_BUILD, new=AsyncMock(side_effect=ValueError("bad region"))):
            result = await service.test_connection("bedrock", {"model": "a-model"})

        assert result == {"success": False, "message": "bad region"}


_NOT_SUPPORTED = " Note: prompt caching is not supported for this model and will be ignored."


@pytest.mark.asyncio
class TestPromptCachingNote:

    async def test_requested_but_unsupported_model_says_so(self, service):
        result = await _test_connection(service, _CapturingModel(), prompt_caching_enabled=True)

        assert result["success"] is True
        assert result["message"] == "Connection successful." + _NOT_SUPPORTED

    async def test_supported_model_reports_plain_success(self, service):
        wrapped = PromptCachingChatModel(inner=_CapturingModel(), cache_style="bedrock_converse")
        result = await _test_connection(service, wrapped, prompt_caching_enabled=True)

        assert result["message"] == "Connection successful."

    @pytest.mark.parametrize("flag", [False, "true", 1, None], ids=repr)
    async def test_no_note_when_caching_was_not_requested(self, service, flag):
        result = await _test_connection(service, _CapturingModel(), prompt_caching_enabled=flag)

        assert result["message"] == "Connection successful."

    async def test_no_note_when_the_flag_is_absent(self, service):
        result = await _test_connection(service, _CapturingModel())

        assert result["message"] == "Connection successful."

    async def test_a_failed_probe_still_reports_the_failure(self, service):
        model = _CapturingModel(error=RuntimeError("no credentials"))
        result = await _test_connection(service, model, prompt_caching_enabled=True)

        assert result == {"success": False, "message": "no credentials"}
