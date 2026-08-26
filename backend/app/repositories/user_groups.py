from typing import List
from uuid import UUID

from injector import inject
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.role import RoleModel
from app.db.models.user_group import UserGroupModel
from app.db.models.user_role import UserRoleModel
from app.db.models.user_supervised_group import UserSupervisedGroupModel
from app.repositories.db_repository import DbRepository


@inject
class UserGroupRepository(DbRepository[UserGroupModel]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserGroupModel, db)

    # ───────────── supervisor assignments ─────────────
    async def user_has_supervisor_role(self, user_id: UUID) -> bool:
        """Return True if the user is assigned the "supervisor" role."""
        result = await self.db.execute(
            select(UserRoleModel)
            .join(RoleModel, RoleModel.id == UserRoleModel.role_id)
            .where(
                UserRoleModel.user_id == user_id,
                RoleModel.name == "supervisor",
            )
        )
        return result.scalars().first() is not None

    async def is_supervisor(self, group_id: UUID, user_id: UUID) -> bool:
        """Return True if the user is already a supervisor of the group."""
        result = await self.db.execute(
            select(UserSupervisedGroupModel).where(
                UserSupervisedGroupModel.group_id == group_id,
                UserSupervisedGroupModel.user_id == user_id,
            )
        )
        return result.scalars().first() is not None

    async def add_supervisor(self, group_id: UUID, user_id: UUID) -> UserSupervisedGroupModel:
        """Assign the user as a supervisor of the group and persist it."""
        link = UserSupervisedGroupModel(group_id=group_id, user_id=user_id)
        self.db.add(link)
        await self.db.flush()
        return link

    async def remove_supervisor(self, group_id: UUID, user_id: UUID) -> None:
        """Remove the user's supervisor assignment from the group."""
        await self.db.execute(
            delete(UserSupervisedGroupModel).where(
                UserSupervisedGroupModel.group_id == group_id,
                UserSupervisedGroupModel.user_id == user_id,
            )
        )
        await self.db.flush()

    async def get_supervisor_user_ids(self, group_id: UUID) -> List[UUID]:
        """Return the user IDs of all supervisors of the group."""
        result = await self.db.execute(
            select(UserSupervisedGroupModel.user_id).where(
                UserSupervisedGroupModel.group_id == group_id
            )
        )
        return list(result.scalars().all())
