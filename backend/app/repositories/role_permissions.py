from typing import Iterable

from fastapi import Depends
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from app.db.models.role_permission import RolePermissionModel
from uuid import UUID

from app.repositories.db_repository import DbRepository
from app.schemas.role_permission import RolePermissionCreate

@inject
class RolePermissionsRepository(DbRepository[RolePermissionModel]):
    """
    Repository for RolePermission join-table operations.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(RolePermissionModel, db)

    async def create(self, data: RolePermissionCreate) -> RolePermissionModel:
        # Idempotent: the (role_id, permission_id) pair is unique in the DB, so
        # re-granting an existing permission returns the row instead of a 500.
        existing = await self._get_pair(data.role_id, data.permission_id)
        if existing:
            return existing

        rp = RolePermissionModel(
            role_id=data.role_id,
            permission_id=data.permission_id,
        )
        self.db.add(rp)
        await self.db.flush()
        await self.db.refresh(rp)
        return rp

    async def get_all(self) -> list[RolePermissionModel]:
        result = await self.db.execute(select(RolePermissionModel))
        return result.scalars().all()

    async def get_links_for_role(self, role_id: UUID) -> list[RolePermissionModel]:
        """Links for one role, so callers never pull the whole join table.

        Deliberately not named ``get_by_role_id`` — the base repository already
        defines that to return the *users* holding a role.
        """
        result = await self.db.execute(
            select(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
        )
        return result.scalars().all()

    async def add_pairs(self, role_id: UUID, permission_ids: Iterable[UUID]) -> int:
        """Insert links for the given permissions. Returns the number added."""
        ids = list(permission_ids)
        if not ids:
            return 0

        self.db.add_all(
            [
                RolePermissionModel(role_id=role_id, permission_id=permission_id)
                for permission_id in ids
            ]
        )
        await self.db.flush()
        return len(ids)

    async def remove_pairs(self, role_id: UUID, permission_ids: Iterable[UUID]) -> int:
        """Delete links for the given permissions. Returns the number removed."""
        ids = list(permission_ids)
        if not ids:
            return 0

        result = await self.db.execute(
            delete(RolePermissionModel)
            .where(RolePermissionModel.role_id == role_id)
            .where(RolePermissionModel.permission_id.in_(ids))
        )
        await self.db.flush()
        return result.rowcount or 0

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
        await self.db.flush()
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
