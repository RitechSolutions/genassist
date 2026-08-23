"""Unit tests for the PROMPT_CACHING_FEATURE_ENABLED withhold on the provider surfaces:
the served form schema, and the update path that must not erase a hidden opt-in"""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config.settings import settings
from app.modules.workflow.llm.provider import LLMProvider
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS_DICT
from app.schemas.llm import LlmProviderUpdate
from app.services.app_settings import AppSettingsService
from app.services.llm_providers import LlmProviderService

_RESIDENCY = "app.services.llm_providers.assert_provider_residency"


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


async def _update(service, stored, **payload) -> dict:
    service.repository.get_by_id.return_value = stored
    with patch(_RESIDENCY, new=AsyncMock()):
        await service.update(uuid4(), LlmProviderUpdate(**payload))
    return stored.connection_data


@pytest.mark.asyncio
class TestUpdatePreservesAHiddenOptIn:
    async def test_an_omitted_key_preserves_the_stored_opt_in(self, service):
        stored = _stored(prompt_caching_enabled=True)
        cd = await _update(service, stored, connection_data={"api_key": "stored-cipher", "temperature": 0.5})

        assert cd["prompt_caching_enabled"] is True

    async def test_an_explicit_false_disables(self, service):
        stored = _stored(prompt_caching_enabled=True)
        cd = await _update(service, stored, connection_data={"prompt_caching_enabled": False})

        assert cd["prompt_caching_enabled"] is False

    async def test_an_explicit_true_enables(self, service):
        cd = await _update(service, _stored(), connection_data={"prompt_caching_enabled": True})

        assert cd["prompt_caching_enabled"] is True

    async def test_a_request_without_connection_data_leaves_it_untouched(self, service):
        stored = _stored(prompt_caching_enabled=True)
        cd = await _update(service, stored, name="renamed")

        assert cd == {"api_key": "stored-cipher", "prompt_caching_enabled": True}

    async def test_the_key_is_never_invented_for_a_provider_that_never_opted_in(self, service):
        cd = await _update(service, _stored(), connection_data={"temperature": 0.5})

        assert "prompt_caching_enabled" not in cd

    async def test_preserving_does_not_look_like_a_connection_data_change(self, service):
        stored = _stored(prompt_caching_enabled=True)
        tested = {"status": "Success", "last_tested_at": "2026-08-23T00:00:00", "message": "ok"}
        stored.connection_status = tested
        await _update(service, stored, connection_data={"api_key": "stored-cipher"})

        assert stored.connection_status == tested


@pytest.mark.asyncio
class TestServedFormSchema:
    async def _serve(self, monkeypatch, enabled: bool) -> dict:
        monkeypatch.setattr(settings, "PROMPT_CACHING_FEATURE_ENABLED", enabled)
        monkeypatch.setattr(settings, "LOCAL_FINE_TUNE_API_URL", "")
        fine_tuning = MagicMock(get_all_by_statuses=AsyncMock(return_value=[]))
        injector = MagicMock(get=MagicMock(return_value=fine_tuning))
        with patch("app.dependencies.injector.injector", injector):
            return await LLMProvider().get_configuration_definitions()

    @staticmethod
    def _providers_offering_the_toggle(schemas: dict) -> list:
        return [
            key
            for key, schema in schemas.items()
            if any(f.get("name") == "prompt_caching_enabled" for f in schema.get("fields") or [])
        ]

    async def test_the_toggle_is_withheld_while_the_flag_is_off(self, monkeypatch):
        schemas = await self._serve(monkeypatch, False)

        assert self._providers_offering_the_toggle(schemas) == []

    async def test_the_toggle_is_offered_while_the_flag_is_on(self, monkeypatch):
        schemas = await self._serve(monkeypatch, True)

        assert self._providers_offering_the_toggle(schemas) == ["anthropic", "bedrock"]

    async def test_every_other_field_survives_the_filter(self, monkeypatch):
        off = await self._serve(monkeypatch, False)
        on = await self._serve(monkeypatch, True)

        for key, schema in on.items():
            expected = [f for f in schema.get("fields") or [] if f["name"] != "prompt_caching_enabled"]
            assert (off[key].get("fields") or []) == expected

    async def test_filtering_never_mutates_the_module_constant(self, monkeypatch):
        before = copy.deepcopy(LLM_FORM_SCHEMAS_DICT)
        await self._serve(monkeypatch, False)

        assert LLM_FORM_SCHEMAS_DICT == before
