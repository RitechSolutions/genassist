"""Unit tests for SalesforceToolNode ("Salesforce Case").

Pure unit tests: the AppSettingsService, SalesforceConnector and
ConversationRepository are mocked, and a lightweight fake state (carrying only
``thread_id``) is used, so no live DB / Redis / network is required.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.utils.encryption_utils import encrypt_key
from app.modules.workflow.engine.nodes.salesforce_tool_node import SalesforceToolNode
from app.schemas.dynamic_form_schemas.app_settings_schemas import (
    get_encrypted_fields_for_type,
)
from app.services.app_settings import AppSettingsService

_NODE_CONFIG = {"type": "salesforceCaseNode", "data": {"name": "Salesforce Case"}}

_APP_SETTINGS_TYPE = "Salesforce"

# Plaintext credentials — the canonical values the connector must ultimately receive.
_APP_SETTINGS_VALUES = {
    "salesforce_instance_url": "https://myorg.my.salesforce.com",
    "salesforce_client_id": "client-id",
    "salesforce_client_secret": "client-secret",
}


def _stored_values():
    """Values as persisted in App Settings: secret fields encrypted at rest, exactly
    as ``AppSettingsService.get_by_id`` returns them (it does NOT decrypt)."""
    encrypted_fields = set(get_encrypted_fields_for_type(_APP_SETTINGS_TYPE))
    return {
        key: (encrypt_key(value) if key in encrypted_fields else value)
        for key, value in _APP_SETTINGS_VALUES.items()
    }


def _make_node(thread_id=None):
    state = SimpleNamespace(thread_id=thread_id)
    return SalesforceToolNode("node-1", _NODE_CONFIG, state)


def _make_app_settings_service():
    service = MagicMock()
    app_settings = SimpleNamespace(type=_APP_SETTINGS_TYPE, values=_stored_values())
    service.get_by_id = AsyncMock(return_value=app_settings)
    return service


def _patch_injector(app_settings_service, conversation_repo=None):
    """Patch the module-level injector so injector.get(...) returns the right mock."""
    fake_injector = MagicMock()

    def _get(dependency):
        if dependency is AppSettingsService:
            return app_settings_service
        return conversation_repo if conversation_repo is not None else MagicMock()

    fake_injector.get.side_effect = _get
    return patch(
        "app.modules.workflow.engine.nodes.salesforce_tool_node.injector",
        fake_injector,
    )


def _patch_connector(create_case_mock):
    connector_instance = MagicMock()
    connector_instance.create_case = create_case_mock
    return patch(
        "app.modules.workflow.engine.nodes.salesforce_tool_node.SalesforceConnector",
        return_value=connector_instance,
    ), connector_instance


@pytest.mark.asyncio
async def test_valid_input_creates_case_and_returns_success_envelope():
    """FR-4/FR-5: valid input -> Case created, success envelope returned."""
    success = {"status": 200, "data": {"id": "500xx", "success": True}}
    create_case = AsyncMock(return_value=success)
    service = _make_app_settings_service()
    app_settings_id = str(uuid.uuid4())

    connector_patch, _ = _patch_connector(create_case)
    node = _make_node()
    with _patch_injector(service), connector_patch:
        result = await node.process(
            {
                "subject": "Help",
                "description": "Something broke",
                "labels": ["billing", "urgent"],
                "custom_fields": [{"key": "Priority", "value": "High"}],
                "app_settings_id": app_settings_id,
            }
        )

    assert result == success
    create_case.assert_awaited_once()
    kwargs = create_case.await_args.kwargs
    assert kwargs["subject"] == "Help"
    assert kwargs["description"] == "Something broke"
    assert kwargs["custom_fields"] == [{"key": "Priority", "value": "High"}]
    # Labels are passed through to the connector for Topic assignment.
    assert kwargs["labels"] == ["billing", "urgent"]


@pytest.mark.asyncio
async def test_encrypted_credentials_are_decrypted_before_use():
    """Regression: secret fields are encrypted at rest; the node MUST decrypt them
    before constructing the connector (otherwise SalesForce rejects the ciphertext
    with ``invalid_client``)."""
    success = {"status": 200, "data": {"id": "500xx"}}
    create_case = AsyncMock(return_value=success)
    service = _make_app_settings_service()

    connector_instance = MagicMock()
    connector_instance.create_case = create_case
    node = _make_node()
    with _patch_injector(service), patch(
        "app.modules.workflow.engine.nodes.salesforce_tool_node.SalesforceConnector",
        return_value=connector_instance,
    ) as connector_cls:
        result = await node.process(
            {
                "subject": "Help",
                "description": "broke",
                "app_settings_id": str(uuid.uuid4()),
            }
        )

    assert result == success
    # The connector must be built with the DECRYPTED plaintext client secret.
    ctor_kwargs = connector_cls.call_args.kwargs
    assert ctor_kwargs["client_secret"] == "client-secret"
    # Non-encrypted fields pass through unchanged.
    assert ctor_kwargs["client_id"] == "client-id"
    assert ctor_kwargs["instance_url"] == "https://myorg.my.salesforce.com"


@pytest.mark.asyncio
async def test_missing_subject_returns_400_without_api_call():
    """FR-9: missing subject -> 400 error, no SalesForce call."""
    create_case = AsyncMock()
    service = _make_app_settings_service()

    connector_patch, _ = _patch_connector(create_case)
    node = _make_node()
    with _patch_injector(service), connector_patch:
        result = await node.process(
            {"description": "x", "app_settings_id": str(uuid.uuid4())}
        )

    assert result["status"] == 400
    create_case.assert_not_called()
    service.get_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_missing_description_returns_400_without_api_call():
    """FR-9: missing description -> 400 error, no SalesForce call."""
    create_case = AsyncMock()
    service = _make_app_settings_service()

    connector_patch, _ = _patch_connector(create_case)
    node = _make_node()
    with _patch_injector(service), connector_patch:
        result = await node.process(
            {"subject": "x", "app_settings_id": str(uuid.uuid4())}
        )

    assert result["status"] == 400
    create_case.assert_not_called()


@pytest.mark.asyncio
async def test_connector_none_result_returns_500():
    """FR-4: connector returns None (failure) -> node owns the 500 envelope."""
    create_case = AsyncMock(return_value=None)
    service = _make_app_settings_service()

    connector_patch, _ = _patch_connector(create_case)
    node = _make_node()
    with _patch_injector(service), connector_patch:
        result = await node.process(
            {
                "subject": "Help",
                "description": "broke",
                "app_settings_id": str(uuid.uuid4()),
            }
        )

    assert result["status"] == 500
    assert "error" in result["data"]


@pytest.mark.asyncio
async def test_connector_exception_returns_500():
    """FR-4: any raised exception -> {"status": 500} error envelope."""
    create_case = AsyncMock(side_effect=RuntimeError("boom"))
    service = _make_app_settings_service()

    connector_patch, _ = _patch_connector(create_case)
    node = _make_node()
    with _patch_injector(service), connector_patch:
        result = await node.process(
            {
                "subject": "Help",
                "description": "broke",
                "app_settings_id": str(uuid.uuid4()),
            }
        )

    assert result["status"] == 500
    assert "error" in result["data"]
