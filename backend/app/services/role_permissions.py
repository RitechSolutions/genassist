from fastapi import Depends
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import ADMIN_ROLE_NAME, is_admin_only_permission
from app.schemas.role_permission import RolePermissionCreate, RolePermissionUpdate

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
