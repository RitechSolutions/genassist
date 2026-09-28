from fastapi import Depends
from injector import inject

from app.cache.redis_cache import invalidate_user_cache
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import ADMIN_ROLE_NAME, is_admin_only_permission
from app.schemas.role_permission import (
    RolePermissionCreate,
    RolePermissionUpdate,
    RolePermissionsSetResult,
)

from app.repositories.permissions import PermissionsRepository
from app.repositories.role_permissions import RolePermissionsRepository
from app.repositories.roles import RolesRepository
from uuid import UUID

@inject
class RolePermissionsService:
    """
    Handles RolePermission-related business logic.
    """

    def __init__(
        self,
        repository: RolePermissionsRepository,
        roles_repository: RolesRepository,
        permissions_repository: PermissionsRepository,
    ):
        self.repository = repository
        self.roles_repository = roles_repository
        self.permissions_repository = permissions_repository

    async def _guard_admin_only_permission(self, role_id: UUID, permission_id: UUID):
        """Reject assigning an admin-only permission to any non-admin role.

        Configuration permissions (File Manager provider, Security settings,
        Feature Flags) must stay reserved for the admin role.
        """
        if role_id is None or permission_id is None:
            return

        permission = await self.permissions_repository.get_by_id(permission_id)
        if permission is None or not is_admin_only_permission(permission.name):
            return

        role = await self.roles_repository.get_by_id(role_id)
        if role is None or role.name != ADMIN_ROLE_NAME:
            raise AppException(ErrorKey.ADMIN_ONLY_PERMISSION, status_code=403)

    async def create(self, data: RolePermissionCreate):
        await self._guard_admin_only_permission(data.role_id, data.permission_id)
        model = await self.repository.create(data)
        return model

    async def get_by_id(self, rp_id: UUID):
        model = await self.repository.get_by_id(rp_id)
        if not model:
            raise AppException(ErrorKey.ROLE_PERMISSION_NOT_FOUND, status_code=404)
        return model

    async def get_all(self):
        models = await self.repository.get_all()
        return models

    async def update(self, rp_id: UUID, data: RolePermissionUpdate):
        existing = await self.repository.get_by_id(rp_id)
        if not existing:
            raise AppException(ErrorKey.ROLE_PERMISSION_NOT_FOUND, status_code=404)

        # Validate the resulting (role, permission) pair after applying the patch.
        target_role_id = data.role_id if data.role_id is not None else existing.role_id
        target_permission_id = (
            data.permission_id if data.permission_id is not None else existing.permission_id
        )
        await self._guard_admin_only_permission(target_role_id, target_permission_id)

        updated = await self.repository.update(rp_id, data)
        if not updated:
            raise AppException(ErrorKey.ROLE_PERMISSION_NOT_FOUND, status_code=404)
        return updated

    async def delete(self, rp_id: UUID):
        existing = await self.repository.get_by_id(rp_id)
        if not existing:
            raise AppException(ErrorKey.ROLE_PERMISSION_NOT_FOUND, status_code=404)
        await self.repository.delete(existing)
        return {"message": f"RolePermission {rp_id} deleted successfully."}

    async def get_permission_ids_for_role(self, role_id: UUID) -> list[UUID]:
        role = await self.roles_repository.get_by_id(role_id)
        if not role:
            raise AppException(ErrorKey.ROLE_NOT_FOUND, status_code=404)

        links = await self.repository.get_links_for_role(role_id)
        return [link.permission_id for link in links]

    async def set_for_role(
        self, role_id: UUID, permission_ids: list[UUID]
    ) -> RolePermissionsSetResult:
        """Replace a role's permissions with `permission_ids` in one transaction.

        The whole set is validated before anything is written, so a rejected
        permission leaves the role untouched rather than half-applied.
        """
        role = await self.roles_repository.get_by_id(role_id)
        if not role:
            raise AppException(ErrorKey.ROLE_NOT_FOUND, status_code=404)

        requested = set(permission_ids)

        # Every requested id must exist, or the caller is silently under-granted.
        found = await self.permissions_repository.get_by_ids(list(requested))
        if len(found) != len(requested):
            raise AppException(ErrorKey.PERMISSION_NOT_FOUND, status_code=404)

        # Admin-only permissions are checked up front, across the whole set.
        if role.name != ADMIN_ROLE_NAME:
            if any(is_admin_only_permission(p.name) for p in found):
                raise AppException(ErrorKey.ADMIN_ONLY_PERMISSION, status_code=403)

        current = {
            link.permission_id
            for link in await self.repository.get_links_for_role(role_id)
        }

        added = await self.repository.add_pairs(role_id, requested - current)
        removed = await self.repository.remove_pairs(role_id, current - requested)

        # Cached auth payloads embed permissions, so holders must be refreshed.
        if added or removed:
            for user in await self.roles_repository.get_by_role_id(role_id):
                await invalidate_user_cache(user.id)

        return RolePermissionsSetResult(
            role_id=role_id,
            permission_ids=sorted(requested, key=str),
            added=added,
            removed=removed,
        )
