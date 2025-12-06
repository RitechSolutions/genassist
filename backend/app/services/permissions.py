from uuid import UUID
from injector import inject
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models import PermissionModel
from app.repositories.permissions import PermissionsRepository
from app.schemas.filter import BaseFilterModel
from app.schemas.permission import PermissionCreate, PermissionUpdate

@inject
class PermissionsService:
    """
    Handles Permission-related business logic.
    """

    def __init__(self, repository: PermissionsRepository):
        self.repository = repository

    async def create(self,data: PermissionCreate):
        model = await self.repository.create_permission(data)
        return model

    async def get_by_id(self, permission_id: UUID):
        model = await self.repository.get_by_id(permission_id)
        if not model:
            raise AppException(error_key=ErrorKey.PERMISSION_NOT_FOUND, status_code=404)
        return model

    async def get_all(self, filter: BaseFilterModel) -> list[PermissionModel]:
        models = await self.repository.get_all(filter_obj=filter)
        return models

    async def delete(self, permission_id: UUID):
        model = await self.get_by_id(permission_id)
        if not model:
            raise AppException(error_key=ErrorKey.PERMISSION_NOT_FOUND, status_code=404)
        await self.repository.delete(model)
        return {"message": f"Permission {permission_id} deleted successfully."}

    async def update(self, permission_id: UUID, data: PermissionUpdate):
        updated_permission = await self.repository.update_permission(permission_id, data)
        if not updated_permission:
            raise AppException(error_key=ErrorKey.PERMISSION_NOT_FOUND, status_code=404)
        return updated_permission
