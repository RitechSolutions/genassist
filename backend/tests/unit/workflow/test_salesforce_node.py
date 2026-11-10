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
from app.modules.workflow.engine.node_result import is_node_failure
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

    failure = is_node_failure(result)
    assert failure is not None and failure["code"] == 400
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

    failure = is_node_failure(result)
    assert failure is not None and failure["code"] == 400
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

    failure = is_node_failure(result)
    assert failure is not None and failure["code"] == 500
    assert "error" in failure["output"]["data"]


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

    failure = is_node_failure(result)
    assert failure is not None and failure["code"] == 500
    assert "error" in failure["output"]["data"]


def _conversation_repo(custom_attributes=None):
    repo = MagicMock()
    repo.fetch_conversation_by_id = AsyncMock(return_value=SimpleNamespace(custom_attributes=custom_attributes))
    repo.update_custom_attributes = AsyncMock()
    return repo


async def _run_node(config, create_case, thread_id=None, repo=None):
    from app.dependencies.injector import injector as shared_injector

    connector_patch, _ = _patch_connector(create_case)
    repo = repo or _conversation_repo()
    with _patch_injector(_make_app_settings_service()), connector_patch, patch.object(
        shared_injector, "get", return_value=repo
    ):
        result = await _make_node(thread_id=thread_id).process(
            {"subject": "Help", "description": "Card failed", "app_settings_id": str(uuid.uuid4()), **config}
        )
    return result, repo


@pytest.mark.asyncio
async def test_contact_boxes_are_sent_as_case_contact_fields():
    create_case = AsyncMock(return_value={"status": 200, "data": {"id": "500xx"}})

    await _run_node({"web_email": " Alice@Example.com ", "web_name": "Alice", "web_phone": ""}, create_case)

    assert create_case.await_args.kwargs["contact_fields"] == {
        "SuppliedEmail": "Alice@Example.com",
        "SuppliedName": "Alice",
    }


@pytest.mark.asyncio
async def test_created_case_saves_the_box_email_and_name_on_the_conversation():
    conversation_id = uuid.uuid4()
    create_case = AsyncMock(return_value={"status": 200, "data": {"id": "500xx"}})

    _, repo = await _run_node(
        {"web_email": "Alice@Example.com", "web_name": "Alice", "custom_fields": [{"key": "SuppliedEmail", "value": "old@example.com"}]},
        create_case,
        thread_id=str(conversation_id),
    )

    repo.update_custom_attributes.assert_awaited_once_with(
        conversation_id, {"pii": {"requester_email": "alice@example.com", "requester_name": "Alice"}}
    )


@pytest.mark.asyncio
async def test_custom_field_email_is_saved_when_the_box_is_empty():
    conversation_id = uuid.uuid4()
    create_case = AsyncMock(return_value={"status": 200, "data": {"id": "500xx"}})

    _, repo = await _run_node(
        {"custom_fields": [{"key": "SuppliedEmail", "value": "Bob@Example.com"}, {"key": "Origin", "value": "Chatbot"}]},
        create_case,
        thread_id=str(conversation_id),
    )

    repo.update_custom_attributes.assert_awaited_once_with(
        conversation_id, {"pii": {"requester_email": "bob@example.com"}}
    )


@pytest.mark.asyncio
async def test_rejected_case_saves_nothing_on_the_conversation():
    create_case = AsyncMock(return_value={"status": 400, "data": {"error": "INVALID_EMAIL_ADDRESS on SuppliedEmail"}})

    result, repo = await _run_node({"web_email": "guest"}, create_case, thread_id=str(uuid.uuid4()))

    assert is_node_failure(result) is not None
    repo.update_custom_attributes.assert_not_awaited()


@pytest.mark.asyncio
async def test_saved_email_matches_what_was_sent():
    conversation_id = uuid.uuid4()
    create_case = AsyncMock(return_value={"status": 200, "data": {"id": "500xx"}})

    _, repo = await _run_node(
        {"web_name": "Dana", "custom_fields": [{"key": "SuppliedEmail", "value": "a@example.com"}, {"key": "SuppliedEmail", "value": ""}]},
        create_case,
        thread_id=str(conversation_id),
    )

    repo.update_custom_attributes.assert_awaited_once_with(conversation_id, {"pii": {"requester_name": "Dana"}})
