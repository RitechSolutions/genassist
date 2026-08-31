"""LlmProviderService prompt-caching seams: the connection probe through a wrapped
model, and the sanitation of the legacy provider-level prompt-caching key"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import botocore.exceptions as botocore_exceptions
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.modules.workflow.llm.prompt_caching_chat_model import PromptCachingChatModel
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.schemas.llm import LlmProviderCreate, LlmProviderUpdate
from app.services.app_settings import AppSettingsService
from app.services.llm_providers import LlmProviderService

_BUILD = "app.modules.workflow.llm.provider.build_chat_model"
_RESIDENCY = "app.services.llm_providers.assert_provider_residency"
_ENCRYPT = "app.services.llm_providers.encrypt_key"
_LEGACY_KEY = "prompt_caching_enabled"


@pytest.fixture
def service():
    return LlmProviderService(
        repository=AsyncMock(spec=LlmProviderRepository),
        app_settings_service=AsyncMock(spec=AppSettingsService),
    )


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


def _stored(**connection_data):
    return SimpleNamespace(
        llm_model_provider="anthropic",
        llm_model="claude-3-opus",
        connection_data={"api_key": "stored-cipher", **connection_data},
        connection_status={"status": "Untested", "last_tested_at": None, "message": None},
    )


async def _create(service, connection_data: dict) -> dict:
    with patch(_RESIDENCY, new=AsyncMock()), patch(_ENCRYPT, side_effect=lambda v: f"enc:{v}"):
        await service.create(
            LlmProviderCreate(
                name="anthropic-1",
                llm_model_provider="anthropic",
                llm_model="claude-3-opus",
                connection_data=connection_data,
            )
        )
    return service.repository.create.await_args.args[0].connection_data


async def _update(service, stored, **payload):
    service.repository.get_by_id.return_value = stored
    with patch(_RESIDENCY, new=AsyncMock()), patch(_ENCRYPT, side_effect=lambda v: f"enc:{v}"):
        await service.update(uuid4(), LlmProviderUpdate(**payload))
    return stored


@pytest.mark.asyncio
class TestCreateStripsTheLegacyKey:
    @pytest.mark.parametrize("value", [True, False, "true", 1], ids=repr)
    async def test_the_key_never_reaches_storage(self, service, value):
        stored = await _create(service, {"api_key": "plain", _LEGACY_KEY: value})

        assert _LEGACY_KEY not in stored

    async def test_the_rest_of_the_payload_survives(self, service):
        stored = await _create(service, {"api_key": "plain", "temperature": 0.5, _LEGACY_KEY: True})

        assert stored["temperature"] == 0.5
        assert stored["api_key"] == "enc:plain"


@pytest.mark.asyncio
class TestUpdateStripsTheLegacyKey:
    async def test_a_resubmitted_key_is_dropped(self, service):
        stored = await _update(
            service, _stored(), connection_data={"api_key": "stored-cipher", "temperature": 0.5, _LEGACY_KEY: True}
        )

        assert _LEGACY_KEY not in stored.connection_data
        assert stored.connection_data["temperature"] == 0.5

    async def test_a_stored_key_is_cleared_on_the_next_save(self, service):
        stored = await _update(
            service, _stored(prompt_caching_enabled=True), connection_data={"api_key": "stored-cipher"}
        )

        assert _LEGACY_KEY not in stored.connection_data

    async def test_the_key_is_never_invented_for_a_clean_provider(self, service):
        stored = await _update(service, _stored(), connection_data={"temperature": 0.5})

        assert _LEGACY_KEY not in stored.connection_data

    async def test_stripping_does_not_look_like_a_connection_data_change(self, service):
        stored = _stored()
        tested = {"status": "Success", "last_tested_at": "2026-08-23T00:00:00", "message": "ok"}
        stored.connection_status = tested

        await _update(service, stored, connection_data={"api_key": "stored-cipher", _LEGACY_KEY: True})

        assert stored.connection_status == tested


@pytest.mark.asyncio
class TestStaleKeyOnlyPayload:

    async def test_stored_credentials_survive(self, service):
        stored = await _update(service, _stored(), connection_data={_LEGACY_KEY: True})

        assert stored.connection_data == {"api_key": "stored-cipher"}

    async def test_stored_connection_status_survives(self, service):
        stored = _stored()
        tested = {"status": "Success", "last_tested_at": "2026-08-23T00:00:00", "message": "ok"}
        stored.connection_status = tested

        await _update(service, stored, connection_data={_LEGACY_KEY: True})

        assert stored.connection_status == tested

    async def test_a_genuinely_empty_payload_keeps_its_existing_semantics(self, service):
        stored = await _update(service, _stored(), connection_data={})

        assert stored.connection_data == {}


class TestTheFormFieldStaysGone:
    def test_no_provider_schema_offers_the_toggle(self):
        offering = [
            key
            for key, schema in LLM_FORM_SCHEMAS_DICT.items()
            if any(f.get("name") == _LEGACY_KEY for f in schema.get("fields") or [])
        ]

        assert offering == []
