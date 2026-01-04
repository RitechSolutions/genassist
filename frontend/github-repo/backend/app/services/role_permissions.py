from fastapi import Depends
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.role_permission import RolePermissionCreate, RolePermissionUpdate

from app.repositories.role_permissions import RolePermissionsRepository
from uuid import UUID

@inject
class RolePermissionsService:
    """
    Handles RolePermission-related business logic.
    """

    def __init__(
        self,
        repository: RolePermissionsRepository
    ):
        self.repository = repository

    async def create(self, data: RolePermissionCreate):
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
