"""Unit tests for the sanitation of the legacy provider-level prompt-caching key"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.schemas.llm import LlmProviderCreate, LlmProviderUpdate
from app.services.app_settings import AppSettingsService
from app.services.llm_providers import LlmProviderService

_RESIDENCY = "app.services.llm_providers.assert_provider_residency"
_ENCRYPT = "app.services.llm_providers.encrypt_key"
_LEGACY_KEY = "prompt_caching_enabled"


@pytest.fixture
def service():
    return LlmProviderService(
        repository=AsyncMock(spec=LlmProviderRepository),
        app_settings_service=AsyncMock(spec=AppSettingsService),
    )


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
