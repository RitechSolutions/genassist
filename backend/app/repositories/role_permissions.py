from fastapi import Depends
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.role_permission import RolePermissionModel
from uuid import UUID

from app.schemas.role_permission import RolePermissionCreate

@inject
class RolePermissionsRepository:
    """
    Repository for RolePermission join-table operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: RolePermissionCreate) -> RolePermissionModel:
        # Optional: check if pair already exists
        existing = await self._get_pair(data.role_id, data.permission_id)
        if existing:
            # Maybe raise exception or skip adding a duplicate
            pass

        rp = RolePermissionModel(
            role_id=data.role_id,
            permission_id=data.permission_id,
        )
        self.db.add(rp)
        await self.db.flush()

        await self.db.commit()
        await self.db.refresh(rp)
        return rp

    async def get_by_id(self, rp_id: UUID) -> RolePermissionModel:
        result = await self.db.execute(
            select(RolePermissionModel).where(RolePermissionModel.id == rp_id)
        )
        return result.scalars().first()

    async def get_all(self) -> list[RolePermissionModel]:
        result = await self.db.execute(select(RolePermissionModel))
        return result.scalars().all()

    async def delete(self, rp: RolePermissionModel):
        await self.db.delete(rp)
        await self.db.commit()

    async def update(
        self, rp_id: UUID, data: RolePermissionCreate
    ) -> RolePermissionModel:
        rp = await self.get_by_id(rp_id)
        if not rp:
            return None

        if data.role_id is not None:
            rp.role_id = data.role_id
        if data.permission_id is not None:
            rp.permission_id = data.permission_id

        self.db.add(rp)
        await self.db.commit()
        await self.db.refresh(rp)
        return rp

    async def _get_pair(self, role_id: UUID, permission_id: UUID) -> RolePermissionModel:
        """Fetch the RolePermission row if it exists, for uniqueness checks."""
        result = await self.db.execute(
            select(RolePermissionModel)
            .where(RolePermissionModel.role_id == role_id)
            .where(RolePermissionModel.permission_id == permission_id)
        )
        return result.scalars().first()
