from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.db_repository import DbRepository
from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.db.models.permission import PermissionModel


@inject
class PermissionsRepository(DbRepository[PermissionModel]):
    """
    Repository for Permission-related database operations.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(PermissionModel, db)

    async def create_permission(self, data: PermissionCreate) -> PermissionModel:
        """
        Creates a new Permission in the database.
        Raises an exception if a duplicate name is detected.
        """
        # Check if permission name already exists
        existing_perm = await self._get_by_name(data.name)
        if existing_perm:
            raise AppException(ErrorKey.PERMISSION_ALREADY_EXISTS)

        new_permission = PermissionModel(
            name=data.name,
            is_active=data.is_active,
            description=data.description,
        )
        # Use the base class create method
        return await self.create(new_permission)

    async def update_permission(
        self, permission_id: UUID, data: PermissionUpdate
    ) -> Optional[PermissionModel]:
        """
        Updates an existing permission.
        """
        permission = await self.get_by_id(permission_id)
        if not permission:
            return None

        if data.name is not None:
            permission.name = data.name
        if data.is_active is not None:
            permission.is_active = data.is_active
        if data.description is not None:
            permission.description = data.description

        # Use the base class update method
        return await self.update(permission)

    async def _get_by_name(self, name: str) -> Optional[PermissionModel]:
        """
        Internal helper to find a permission by name.
        """
        result = await self.db.execute(
            select(PermissionModel).where(PermissionModel.name == name)
        )
        return result.scalars().first()