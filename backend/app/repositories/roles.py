from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models.role import RoleModel
from app.repositories.db_repository import DbRepository
from app.schemas.role import RoleCreate
from fastapi import Depends
from app.db.session import get_db
from starlette_context import context


class RolesRepository(DbRepository[RoleModel]):
    def __init__(self, db: AsyncSession = Depends(get_db)):
        super().__init__(RoleModel, db)


    async def create(self, role: RoleCreate):
        new_role = RoleModel(name=role.name, is_active=role.is_active)
        self.db.add(new_role)
        await self.db.commit()
        await self.db.refresh(new_role)
        return new_role


    async def update(self, role: RoleModel):
        self.db.add(role)
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def get_all_by_ids(self, ids: list[int]) -> list[RoleModel]:
        result = await self.db.execute(select(RoleModel).where(RoleModel.id.in_(ids)))
        return result.scalars().all()

    async def get_by_name(self, name: str) -> RoleModel:
        result = await self.db.execute(select(RoleModel).where(RoleModel.name == name))
        return result.scalars().first()