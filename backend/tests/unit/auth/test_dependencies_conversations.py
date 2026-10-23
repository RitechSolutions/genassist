"""Unit tests for conversation-scoped auth dependencies."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette_context import context, request_cycle_context

from app.auth.dependencies_conversations import (
    _handle_authenticated_agent,
    _handle_guest_token,
    permissions_for_conversation,
)
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P


def _make_request(*, guest_token=None, api_key=None, user=None, agent=None):
    request = MagicMock()
    request.state = SimpleNamespace(
        guest_token=guest_token,
        api_key=api_key,
        user=user,
        agent=agent,
    )
    return request


def _agent(token_based_auth: bool):
    return SimpleNamespace(
        security_settings=SimpleNamespace(token_based_auth=token_based_auth),
    )


@pytest.mark.asyncio
async def test_permissions_for_conversation_checks_guest_token():
    check = permissions_for_conversation(P.Conversation.UPDATE_IN_PROGRESS)
    request = _make_request(
        guest_token={"permissions": [P.Conversation.UPDATE_IN_PROGRESS]},
    )
    with request_cycle_context():
        context["auth_mode"] = "guest_token"
        await check(request)


@pytest.mark.asyncio
async def test_permissions_for_conversation_rejects_guest_without_permission():
    check = permissions_for_conversation(P.Conversation.READ)
    request = _make_request(
        guest_token={"permissions": [P.Conversation.UPDATE_IN_PROGRESS]},
    )
    with request_cycle_context():
        context["auth_mode"] = "guest_token"
        with pytest.raises(AppException) as exc:
            await check(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_permissions_for_conversation_ignores_stale_guest_token_for_jwt_user():
    """JWT/API-key callers must not be limited to guest_token permissions."""
    check = permissions_for_conversation(P.Conversation.READ)
    user = SimpleNamespace(permissions=[P.Conversation.READ])
    request = _make_request(
        guest_token={"permissions": [P.Conversation.UPDATE_IN_PROGRESS]},
        user=user,
    )
    with request_cycle_context():
        context["auth_mode"] = "token"
        await check(request)


@pytest.mark.asyncio
async def test_permissions_for_conversation_checks_api_key_in_legacy_mode():
    check = permissions_for_conversation(P.Conversation.READ)
    api_key = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(api_key=api_key, agent=_agent(token_based_auth=False))
    with request_cycle_context():
        context["auth_mode"] = "api_key"
        with pytest.raises(AppException) as exc:
            await check(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_permissions_for_conversation_allows_legacy_api_key_with_permission():
    check = permissions_for_conversation(P.Conversation.UPDATE_IN_PROGRESS)
    api_key = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(api_key=api_key, agent=_agent(token_based_auth=False))
    with request_cycle_context():
        context["auth_mode"] = "api_key"
        await check(request)


@pytest.mark.asyncio
async def test_permissions_for_conversation_checks_api_key_when_token_based_auth_enabled():
    check = permissions_for_conversation(P.Conversation.READ)
    api_key = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(api_key=api_key, agent=_agent(token_based_auth=True))
    with request_cycle_context():
        context["auth_mode"] = "api_key"
        with pytest.raises(AppException) as exc:
            await check(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_permissions_for_conversation_always_checks_jwt_user():
    check = permissions_for_conversation(P.Conversation.READ)
    user = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(user=user)
    with request_cycle_context():
        context["auth_mode"] = "token"
        with pytest.raises(AppException) as exc:
            await check(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_guest_token_sets_user_permissions_in_context():
    """Nodes read permissions from the request context, so guest auth must fill it."""
    conversation_id = uuid4()
    auth_service = MagicMock()
    auth_service.decode_guest_token = AsyncMock(
        return_value={
            "conversation_id": str(conversation_id),
            "user_id": str(uuid4()),
            "permissions": [P.Conversation.UPDATE_IN_PROGRESS],
        }
    )
    request = _make_request()
    with request_cycle_context():
        handled = await _handle_guest_token(request, "tok", conversation_id, auth_service, agent=None)
        assert handled is True
        assert context["user_permissions"] == [P.Conversation.UPDATE_IN_PROGRESS]


@pytest.mark.asyncio
async def test_token_based_agent_sets_user_permissions_in_context():
    """A signed-in user on a token_based_auth agent keeps their permissions in context."""
    user = SimpleNamespace(id=uuid4(), roles=["admin"], permissions=["*"], operator=None)
    request = _make_request(agent=_agent(token_based_auth=True))
    with patch("app.auth.dependencies_conversations.oauth2", AsyncMock(return_value=None)):
        with request_cycle_context():
            await _handle_authenticated_agent(request, uuid4(), request.state.agent, None, user, MagicMock())
            assert context["user_permissions"] == ["*"]
