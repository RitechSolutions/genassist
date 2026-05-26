"""Unit tests for conversation-scoped auth dependencies."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from starlette_context import context, request_cycle_context

from app.auth.dependencies_conversations import permissions_for_conversation
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
