from uuid import UUID

from injector import inject
from sqlalchemy import delete, select

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.role import RoleModel
from app.db.models.user_group import UserGroupModel
from app.db.models.user_role import UserRoleModel
from app.db.models.user_supervised_group import UserSupervisedGroupModel
from app.repositories.user_groups import UserGroupRepository
from app.schemas.user_group import UserGroupCreate, UserGroupRead, UserGroupUpdate


@inject
class UserGroupService:
    def __init__(self, repository: UserGroupRepository):
        self.repository = repository

    async def get_all(self) -> list[UserGroupRead]:
        groups = await self.repository.get_all()
        return [UserGroupRead.model_validate(g) for g in groups]

    async def get_by_id(self, group_id: UUID) -> UserGroupRead:
        group = await self.repository.get_by_id(group_id)
        if not group:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        return UserGroupRead.model_validate(group)

    async def create(self, data: UserGroupCreate) -> UserGroupRead:
        obj = UserGroupModel(**data.model_dump())
        created = await self.repository.create(obj)
        return UserGroupRead.model_validate(created)

    async def update(self, group_id: UUID, data: UserGroupUpdate) -> UserGroupRead:
        group = await self.repository.get_by_id(group_id)
        if not group:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(group, field, value)
        updated = await self.repository.update(group)
        return UserGroupRead.model_validate(updated)

    async def delete(self, group_id: UUID) -> dict:
        group = await self.repository.get_by_id(group_id)
        if not group:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        await self.repository.delete(group)
        return {"message": f"Deleted user group {group_id}"}

    async def add_supervisor(self, group_id: UUID, user_id: UUID) -> dict:
        group = await self.repository.get_by_id(group_id)
        if not group:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        # Verify the user has the supervisor role
        role_check = await self.repository.db.execute(
            select(UserRoleModel).join(RoleModel, RoleModel.id == UserRoleModel.role_id).where(
                UserRoleModel.user_id == user_id,
                RoleModel.name == "supervisor",
            )
        )
        if not role_check.scalars().first():
            raise AppException(
                error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                status_code=400,
            )
        # Check not already assigned
        existing = await self.repository.db.execute(
            select(UserSupervisedGroupModel).where(
                UserSupervisedGroupModel.group_id == group_id,
                UserSupervisedGroupModel.user_id == user_id,
            )
        )
        if existing.scalars().first():
            return {"message": "User is already a supervisor of this group"}
        obj = UserSupervisedGroupModel(group_id=group_id, user_id=user_id)
        self.repository.db.add(obj)
        await self.repository.db.commit()
        return {"message": f"User {user_id} added as supervisor of group {group_id}"}

    async def remove_supervisor(self, group_id: UUID, user_id: UUID) -> dict:
        group = await self.repository.get_by_id(group_id)
        if not group:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        await self.repository.db.execute(
            delete(UserSupervisedGroupModel).where(
                UserSupervisedGroupModel.group_id == group_id,
                UserSupervisedGroupModel.user_id == user_id,
            )
        )
        await self.repository.db.commit()
        return {"message": f"User {user_id} removed as supervisor of group {group_id}"}

    async def get_supervisors(self, group_id: UUID) -> list[UUID]:
        group = await self.repository.get_by_id(group_id)
        if not group:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        result = await self.repository.db.execute(
            select(UserSupervisedGroupModel.user_id).where(
                UserSupervisedGroupModel.group_id == group_id
            )
        )
        return list(result.scalars().all())