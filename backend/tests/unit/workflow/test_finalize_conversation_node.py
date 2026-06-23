"""Unit tests for FinalizeConversationNode ("End Conversation").

Pure unit tests: the ConversationService is mocked and a lightweight fake state
(carrying only ``thread_id``) is used, so no live DB / Redis is required.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.finalize_conversation_node import FinalizeConversationNode
from app.schemas.dynamic_form_schemas.nodes import NODE_HANDLERS_SCHEMAS

_NODE_CONFIG = {"type": "finalizeConversationNode", "data": {"name": "End Conversation"}}


def _make_node(thread_id):
    """Build a FinalizeConversationNode over a fake state carrying only thread_id."""
    state = SimpleNamespace(thread_id=thread_id)
    return FinalizeConversationNode("node-1", _NODE_CONFIG, state)


def _patch_service(service_mock):
    """Patch the module-level injector so injector.get(...) returns service_mock."""
    fake_injector = MagicMock()
    fake_injector.get.return_value = service_mock
    return patch(
        "app.modules.workflow.engine.nodes.finalize_conversation_node.injector",
        fake_injector,
    )


@pytest.mark.asyncio
async def test_happy_path_finalizes_conversation_from_thread_id():
    """AC-1/AC-2/FR-6: finalize called once with conversation_id (keyword) from thread_id."""
    conversation_id = uuid.uuid4()
    service = MagicMock()
    service.finalize_in_progress_conversation = AsyncMock(return_value=MagicMock())

    node = _make_node(str(conversation_id))
    with _patch_service(service):
        result = await node.process({})

    service.finalize_in_progress_conversation.assert_awaited_once_with(conversation_id=conversation_id)
    assert result == {
        "status": "success",
        "finalized": True,
        "conversation_id": str(conversation_id),
    }


@pytest.mark.asyncio
async def test_already_finalized_is_handled_no_op():
    """AC-4: CONVERSATION_FINALIZED -> handled no-op, no exception raised."""
    conversation_id = uuid.uuid4()
    service = MagicMock()
    service.finalize_in_progress_conversation = AsyncMock(side_effect=AppException(ErrorKey.CONVERSATION_FINALIZED))

    node = _make_node(str(conversation_id))
    with _patch_service(service):
        result = await node.process({})

    assert result["status"] == "skipped"
    assert result["reason"] == ErrorKey.CONVERSATION_FINALIZED.value


@pytest.mark.asyncio
async def test_not_found_is_handled_no_op():
    """AC-5: CONVERSATION_NOT_FOUND -> handled no-op, no exception raised."""
    conversation_id = uuid.uuid4()
    service = MagicMock()
    service.finalize_in_progress_conversation = AsyncMock(side_effect=AppException(ErrorKey.CONVERSATION_NOT_FOUND))

    node = _make_node(str(conversation_id))
    with _patch_service(service):
        result = await node.process({})

    assert result["status"] == "skipped"
    assert result["reason"] == ErrorKey.CONVERSATION_NOT_FOUND.value


@pytest.mark.asyncio
async def test_thread_id_none_is_no_op_without_calling_service():
    """AC-5/FR-9: no resolvable conversation (thread_id None) -> no-op, service untouched."""
    service = MagicMock()
    service.finalize_in_progress_conversation = AsyncMock()

    node = _make_node(None)
    with _patch_service(service):
        result = await node.process({})

    service.finalize_in_progress_conversation.assert_not_called()
    assert result == {"status": "skipped", "reason": "no_conversation"}


@pytest.mark.asyncio
async def test_thread_id_non_uuid_is_no_op_without_calling_service():
    """AC-5/FR-9: thread_id that is not a UUID -> no-op, service untouched."""
    service = MagicMock()
    service.finalize_in_progress_conversation = AsyncMock()

    node = _make_node("not-a-uuid")
    with _patch_service(service):
        result = await node.process({})

    service.finalize_in_progress_conversation.assert_not_called()
    assert result == {"status": "skipped", "reason": "no_conversation"}


@pytest.mark.asyncio
async def test_empty_messages_surfaces_error():
    """AC-6/FR-8: EMPTY_MESSAGES_FOR_CONVERSATION is surfaced (re-raised), not a no-op."""
    conversation_id = uuid.uuid4()
    service = MagicMock()
    service.finalize_in_progress_conversation = AsyncMock(
        side_effect=AppException(ErrorKey.EMPTY_MESSAGES_FOR_CONVERSATION)
    )

    node = _make_node(str(conversation_id))
    with _patch_service(service), pytest.raises(AppException) as exc_info:
        await node.process({})

    assert exc_info.value.error_key == ErrorKey.EMPTY_MESSAGES_FOR_CONVERSATION


def test_pass_through_declares_input_and_output_handlers():
    """AC-7/FR-7: pass-through node exposes both an input (target) and output (source) handler.

    A full engine run is heavy (needs DB/Redis/LLM), so non-halt is asserted structurally:
    declaring a ``source`` (output) handler is what lets a downstream node be wired and
    executed after this node (the engine traverses outgoing edges from source handlers).
    """
    handlers = NODE_HANDLERS_SCHEMAS["finalizeConversationNode"]
    types = {h["type"] for h in handlers}
    assert "target" in types  # input handler
    assert "source" in types  # output handler -> downstream nodes still run
