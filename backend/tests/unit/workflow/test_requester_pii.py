"""Requester PII saved on the conversation for GDPR lookups (Zendesk behaviour pinned)."""

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.dependencies.injector import injector
from app.modules.workflow.engine.nodes.zendesk_tool_node import ZendeskToolNode

_ZENDESK_CONFIG = {"type": "zendeskTicketNode", "data": {"name": "Zendesk Ticket"}}


def _zendesk_node(thread_id):
    return ZendeskToolNode("node-1", _ZENDESK_CONFIG, SimpleNamespace(thread_id=thread_id))


def _repo(conversation):
    repo = MagicMock()
    repo.fetch_conversation_by_id = AsyncMock(return_value=conversation)
    repo.update_custom_attributes = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_zendesk_stores_lowercased_email_and_trimmed_name_keeping_other_attributes():
    conversation_id = uuid.uuid4()
    conversation = SimpleNamespace(custom_attributes={"region": "EU", "pii": {"phone": "123"}})
    repo = _repo(conversation)

    with patch.object(injector, "get", return_value=repo):
        await _zendesk_node(str(conversation_id))._persist_pii_to_conversation(
            requester_email="  Alice@Example.COM ", requester_name="  Alice Smith  "
        )

    repo.update_custom_attributes.assert_awaited_once_with(
        conversation_id,
        {
            "region": "EU",
            "pii": {"phone": "123", "requester_email": "alice@example.com", "requester_name": "Alice Smith"},
        },
    )


@pytest.mark.asyncio
async def test_zendesk_stores_email_without_name():
    conversation_id = uuid.uuid4()
    repo = _repo(SimpleNamespace(custom_attributes=None))

    with patch.object(injector, "get", return_value=repo):
        await _zendesk_node(str(conversation_id))._persist_pii_to_conversation(
            requester_email="bob@example.com", requester_name=None
        )

    repo.update_custom_attributes.assert_awaited_once_with(
        conversation_id, {"pii": {"requester_email": "bob@example.com"}}
    )


@pytest.mark.asyncio
async def test_zendesk_does_nothing_without_email_or_name():
    with patch.object(injector, "get") as get:
        await _zendesk_node(str(uuid.uuid4()))._persist_pii_to_conversation(requester_email="", requester_name=None)

    get.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("thread_id", [None, "", "not-a-uuid"])
async def test_zendesk_does_nothing_without_a_valid_conversation_id(thread_id):
    repo = _repo(SimpleNamespace(custom_attributes={}))

    with patch.object(injector, "get", return_value=repo):
        await _zendesk_node(thread_id)._persist_pii_to_conversation(
            requester_email="bob@example.com", requester_name="Bob"
        )

    repo.update_custom_attributes.assert_not_awaited()


@pytest.mark.asyncio
async def test_zendesk_does_nothing_when_the_conversation_is_missing():
    repo = _repo(None)

    with patch.object(injector, "get", return_value=repo):
        await _zendesk_node(str(uuid.uuid4()))._persist_pii_to_conversation(
            requester_email="bob@example.com", requester_name="Bob"
        )

    repo.update_custom_attributes.assert_not_awaited()


@pytest.mark.asyncio
async def test_zendesk_database_error_is_logged_and_never_raised():
    repo = _repo(SimpleNamespace(custom_attributes={}))
    repo.update_custom_attributes = AsyncMock(side_effect=RuntimeError("db down"))

    with patch.object(injector, "get", return_value=repo), patch.object(logging.Logger, "warning") as warning:
        await _zendesk_node(str(uuid.uuid4()))._persist_pii_to_conversation(
            requester_email="bob@example.com", requester_name="Bob"
        )

    warning.assert_called_once()
    assert warning.call_args.args[0] == (
        "Zendesk node: failed to persist PII to conversation custom_attributes: %s"
    )


@pytest.mark.asyncio
async def test_database_error_log_leaves_out_the_saved_values():
    repo = _repo(SimpleNamespace(custom_attributes={}))
    repo.update_custom_attributes = AsyncMock(
        side_effect=RuntimeError("UPDATE failed [parameters: {'requester_email': 'bob@example.com', 'requester_name': 'Bob Stone'}]")
    )

    with patch.object(injector, "get", return_value=repo), patch.object(logging.Logger, "warning") as warning:
        await _zendesk_node(str(uuid.uuid4()))._persist_pii_to_conversation(
            requester_email="bob@example.com", requester_name="Bob Stone"
        )

    logged = " ".join(str(arg) for arg in warning.call_args.args)
    assert "RuntimeError" in logged
    assert "bob@example.com" not in logged
    assert "Bob Stone" not in logged
