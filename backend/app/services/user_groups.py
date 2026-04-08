from uuid import UUID

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.user_group import UserGroupModel
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