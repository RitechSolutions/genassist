"""Unit tests for the bulk RolePermissionsService.set_for_role().

The repositories are mocked, so no database or app bootstrap is needed. These
cover the diffing, the up-front validation that keeps a rejected set from being
half-applied, and the admin-only guard on the bulk path.
"""
import asyncio
import types
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.services.role_permissions import RolePermissionsService


def _permission(permission_id, name):
    return types.SimpleNamespace(id=permission_id, name=name)


def _make_service(role_name="supervisor", current_ids=(), catalog=None):
    """Wire a service whose role holds `current_ids` and whose catalog is `catalog`."""
    repo = AsyncMock()
    roles_repo = AsyncMock()
    permissions_repo = AsyncMock()

    roles_repo.get_by_id.return_value = types.SimpleNamespace(name=role_name)
    roles_repo.get_by_role_id.return_value = []

    repo.get_links_for_role.return_value = [
        types.SimpleNamespace(permission_id=permission_id) for permission_id in current_ids
    ]
    repo.add_pairs.side_effect = lambda _role_id, ids: len(list(ids))
    repo.remove_pairs.side_effect = lambda _role_id, ids: len(list(ids))

    permissions_repo.get_by_ids.side_effect = lambda ids: [
        (catalog or {})[permission_id] for permission_id in ids if permission_id in (catalog or {})
    ]

    return RolePermissionsService(repo, roles_repo, permissions_repo), repo


def _run(coro):
    return asyncio.run(coro)


def test_adds_and_removes_only_the_difference():
    keep, drop, add = uuid4(), uuid4(), uuid4()
    catalog = {
        keep: _permission(keep, "read:workflow"),
        add: _permission(add, "create:workflow"),
    }
    service, repo = _make_service(current_ids=(keep, drop), catalog=catalog)

    result = _run(service.set_for_role(uuid4(), [keep, add]))

    assert repo.add_pairs.await_args.args[1] == {add}
    assert repo.remove_pairs.await_args.args[1] == {drop}
    assert result.added == 1
    assert result.removed == 1


def test_empty_set_clears_every_permission():
    held = uuid4()
    service, repo = _make_service(current_ids=(held,), catalog={})

    result = _run(service.set_for_role(uuid4(), []))

    assert repo.remove_pairs.await_args.args[1] == {held}
    assert result.removed == 1
    assert result.permission_ids == []


def test_duplicate_ids_in_the_request_are_collapsed():
    permission_id = uuid4()
    catalog = {permission_id: _permission(permission_id, "read:workflow")}
    service, repo = _make_service(catalog=catalog)

    result = _run(service.set_for_role(uuid4(), [permission_id, permission_id]))

    assert repo.add_pairs.await_args.args[1] == {permission_id}
    assert result.added == 1


def test_unknown_permission_id_is_rejected_before_any_write():
    known, unknown = uuid4(), uuid4()
    catalog = {known: _permission(known, "read:workflow")}
    service, repo = _make_service(catalog=catalog)

    with pytest.raises(AppException) as exc_info:
        _run(service.set_for_role(uuid4(), [known, unknown]))

    assert exc_info.value.error_key == ErrorKey.PERMISSION_NOT_FOUND
    repo.add_pairs.assert_not_called()
    repo.remove_pairs.assert_not_called()


def test_missing_role_is_rejected():
    service, repo = _make_service()
    service.roles_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as exc_info:
        _run(service.set_for_role(uuid4(), []))

    assert exc_info.value.error_key == ErrorKey.ROLE_NOT_FOUND
    repo.remove_pairs.assert_not_called()


def test_admin_only_permission_blocked_for_non_admin_role_and_nothing_written():
    reserved = uuid4()
    catalog = {reserved: _permission(reserved, "read:feature_flag")}
    service, repo = _make_service(role_name="supervisor", catalog=catalog)

    with pytest.raises(AppException) as exc_info:
        _run(service.set_for_role(uuid4(), [reserved]))

    assert exc_info.value.error_key == ErrorKey.ADMIN_ONLY_PERMISSION
    assert exc_info.value.status_code == 403
    repo.add_pairs.assert_not_called()
    repo.remove_pairs.assert_not_called()


def test_admin_only_permission_allowed_for_the_admin_role():
    reserved = uuid4()
    catalog = {reserved: _permission(reserved, "read:feature_flag")}
    service, repo = _make_service(role_name="admin", catalog=catalog)

    result = _run(service.set_for_role(uuid4(), [reserved]))

    assert result.added == 1
    repo.add_pairs.assert_awaited_once()


def test_holders_of_the_role_have_their_cache_invalidated():
    added = uuid4()
    catalog = {added: _permission(added, "read:workflow")}
    service, _ = _make_service(catalog=catalog)
    user = types.SimpleNamespace(id=uuid4())
    service.roles_repository.get_by_role_id.return_value = [user]

    with patch(
        "app.services.role_permissions.invalidate_user_cache", new=AsyncMock()
    ) as invalidate:
        _run(service.set_for_role(uuid4(), [added]))

    invalidate.assert_awaited_once_with(user.id)


def test_no_cache_invalidation_when_the_set_is_unchanged():
    held = uuid4()
    catalog = {held: _permission(held, "read:workflow")}
    service, _ = _make_service(current_ids=(held,), catalog=catalog)
    service.roles_repository.get_by_role_id.return_value = [
        types.SimpleNamespace(id=uuid4())
    ]

    with patch(
        "app.services.role_permissions.invalidate_user_cache", new=AsyncMock()
    ) as invalidate:
        result = _run(service.set_for_role(uuid4(), [held]))

    assert (result.added, result.removed) == (0, 0)
    invalidate.assert_not_awaited()
