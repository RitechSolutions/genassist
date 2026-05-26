"""Unit tests for conversation-scoped auth dependencies."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
    await check(request)


@pytest.mark.asyncio
async def test_permissions_for_conversation_rejects_guest_without_permission():
    check = permissions_for_conversation(P.Conversation.READ)
    request = _make_request(
        guest_token={"permissions": [P.Conversation.UPDATE_IN_PROGRESS]},
    )
    with pytest.raises(AppException) as exc:
        await check(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_permissions_for_conversation_checks_api_key_in_legacy_mode():
    check = permissions_for_conversation(P.Conversation.READ)
    api_key = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(api_key=api_key, agent=_agent(token_based_auth=False))
    with pytest.raises(AppException) as exc:
        await check(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_permissions_for_conversation_allows_legacy_api_key_with_permission():
    check = permissions_for_conversation(P.Conversation.UPDATE_IN_PROGRESS)
    api_key = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(api_key=api_key, agent=_agent(token_based_auth=False))
    await check(request)


@pytest.mark.asyncio
async def test_permissions_for_conversation_checks_api_key_when_token_based_auth_enabled():
    check = permissions_for_conversation(P.Conversation.READ)
    api_key = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(api_key=api_key, agent=_agent(token_based_auth=True))
    with pytest.raises(AppException) as exc:
        await check(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_permissions_for_conversation_always_checks_jwt_user():
    check = permissions_for_conversation(P.Conversation.READ)
    user = SimpleNamespace(permissions=[P.Conversation.UPDATE_IN_PROGRESS])
    request = _make_request(user=user)
    with pytest.raises(AppException) as exc:
        await check(request)
    assert exc.value.status_code == 403
