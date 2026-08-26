"""Unit tests for the admin-only permission guard in RolePermissionsService.

These tests mock the repositories, so no database or app bootstrap is needed.
They verify that configuration permissions (app_settings / feature_flag) can
only be assigned to the `admin` role.
"""
import asyncio
import types
from uuid import uuid4

import pytest
from unittest.mock import AsyncMock

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.role_permission import RolePermissionCreate, RolePermissionUpdate
from app.services.role_permissions import RolePermissionsService


def _make_service(role_name: str, permission_name: str):
    repo = AsyncMock()
    roles_repo = AsyncMock()
    permissions_repo = AsyncMock()

    roles_repo.get_by_id.return_value = types.SimpleNamespace(name=role_name)
    permissions_repo.get_by_id.return_value = types.SimpleNamespace(name=permission_name)

    # For the update path, the existing row carries a role/permission pair.
    repo.get_by_id.return_value = types.SimpleNamespace(
        role_id=uuid4(), permission_id=uuid4()
    )
    repo.create.return_value = "created"
    repo.update.return_value = "updated"

    service = RolePermissionsService(repo, roles_repo, permissions_repo)
    return service, repo


def test_admin_only_permission_blocked_for_non_admin_role():
    service, repo = _make_service("supervisor", "read:feature_flag")
    data = RolePermissionCreate(role_id=uuid4(), permission_id=uuid4())

    with pytest.raises(AppException) as exc_info:
        asyncio.run(service.create(data))

    assert exc_info.value.error_key == ErrorKey.ADMIN_ONLY_PERMISSION
    assert exc_info.value.status_code == 403
    repo.create.assert_not_called()


def test_app_settings_permission_blocked_for_non_admin_role():
    service, repo = _make_service("operator", "update:app_settings")
    data = RolePermissionCreate(role_id=uuid4(), permission_id=uuid4())

    with pytest.raises(AppException) as exc_info:
        asyncio.run(service.create(data))

    assert exc_info.value.error_key == ErrorKey.ADMIN_ONLY_PERMISSION
    repo.create.assert_not_called()


def test_admin_only_permission_allowed_for_admin_role():
    service, repo = _make_service("admin", "read:feature_flag")
    data = RolePermissionCreate(role_id=uuid4(), permission_id=uuid4())

    result = asyncio.run(service.create(data))

    assert result == "created"
    repo.create.assert_awaited_once()


def test_non_admin_only_permission_allowed_for_non_admin_role():
    service, repo = _make_service("supervisor", "read:operator")
    data = RolePermissionCreate(role_id=uuid4(), permission_id=uuid4())

    result = asyncio.run(service.create(data))

    assert result == "created"
    repo.create.assert_awaited_once()


def test_update_to_admin_only_permission_blocked_for_non_admin_role():
    service, repo = _make_service("supervisor", "delete:feature_flag")
    data = RolePermissionUpdate(permission_id=uuid4())

    with pytest.raises(AppException) as exc_info:
        asyncio.run(service.update(uuid4(), data))

    assert exc_info.value.error_key == ErrorKey.ADMIN_ONLY_PERMISSION
    repo.update.assert_not_called()
