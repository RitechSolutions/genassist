from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

from uuid import UUID

from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.db.models.permission import PermissionModel
class PermissionsRepository:
    """
    Repository for Permission-related database operations.
    """

    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    async def create(self, data: PermissionCreate) -> PermissionModel:
        """
        Creates a new Permission in the database.
        Raises an exception if a duplicate name is detected, or handle it as you see fit.
        """
        # (Optional) check if permission name already exists
        existing_perm = await self._get_by_name(data.name)
        if existing_perm:
           raise AppException(ErrorKey.PERMISSION_ALREADY_EXISTS)

        new_permission = PermissionModel(
            name=data.name,
            is_active=data.is_active,

            description=data.description,
        )
        self.db.add(new_permission)
        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(new_permission)
        return new_permission

    async def get_by_id(self, permission_id: UUID) -> PermissionModel:
        result = await self.db.execute(
            select(PermissionModel)
            .where(PermissionModel.id == permission_id)
        )
        return result.scalars().first()

    async def get_all(self) -> list[PermissionModel]:
        result = await self.db.execute(select(PermissionModel))
        return result.scalars().all()

    async def delete(self, permission: PermissionModel):
        await self.db.delete(permission)
        await self.db.commit()

    async def update(
        self, permission_id: UUID, data: PermissionUpdate
    ) -> PermissionModel:
        permission = await self.get_by_id(permission_id)
        if not permission:
            return None

        if data.name is not None:
            permission.name = data.name
        if data.is_active is not None:
            permission.is_active = data.is_active
        if data.description is not None:
            permission.description = data.description

        self.db.add(permission)
        await self.db.commit()
        await self.db.refresh(permission)
        return permission

    async def _get_by_name(self, name: str) -> PermissionModel:
        result = await self.db.execute(
            select(PermissionModel).where(PermissionModel.name == name)
        )
        return result.scalars().first()
