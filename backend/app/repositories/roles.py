from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.sql_alchemy_utils import add_dynamic_ordering, add_pagination
from app.db.models.api_key_role import ApiKeyRoleModel
from app.db.models.role import RoleModel
from app.db.models.user_role import UserRoleModel
from app.repositories.db_repository import DbRepository
from app.schemas.filter import BaseFilterModel
from app.schemas.role import RoleCreate

@inject
class RolesRepository(DbRepository[RoleModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(RoleModel, db)


    async def create_role(self, role: RoleCreate):
        new_role = RoleModel(**role.model_dump())
        return await self.create(new_role)

    async def get_all_by_ids(self, ids: list[int]) -> list[RoleModel]:
        result = await self.db.execute(select(RoleModel).where(RoleModel.id.in_(ids)))
        return result.scalars().all()

    async def get_by_name(self, name: str) -> RoleModel:
        result = await self.db.execute(select(RoleModel).where(RoleModel.name == name))
        return result.scalars().first()

    async def count_assignments_for_role(self, role_id: UUID) -> tuple[int, int]:
        """Returns (user_role_row_count, api_key_role_row_count) for this role."""
        user_q = select(func.count()).select_from(UserRoleModel).where(
            UserRoleModel.role_id == role_id
        )
        api_q = select(func.count()).select_from(ApiKeyRoleModel).where(
            ApiKeyRoleModel.role_id == role_id
        )
        user_count = (await self.db.execute(user_q)).scalar_one()
        api_count = (await self.db.execute(api_q)).scalar_one()
        return user_count, api_count