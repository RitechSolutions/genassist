from injector import inject
from sqlalchemy import UUID

from app.cache.redis_cache import invalidate_user_cache
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models import RoleModel
from app.repositories.roles import RolesRepository
from app.schemas.filter import BaseFilterModel
from app.schemas.role import RoleCreate, RoleUpdate


@inject
class RolesService:
    def __init__(self, repository: RolesRepository):
        self.repository = repository

    async def create(self, role: RoleCreate):
        return await self.repository.create_role(role)

    async def get_all(self, filter: BaseFilterModel = None) -> list[RoleModel]:
        models = await self.repository.get_all(filter_obj=filter)
        return models

    async def get_by_id(self, role_id: UUID):
        model = await self.repository.get_by_id(role_id)
        if not model:
            raise AppException(
                error_key=ErrorKey.ROLE_NOT_FOUND, status_code=404)
        return model

    async def update_partial(self, role_id: UUID, update_data: RoleUpdate):
        model = await self.get_by_id(role_id)

        if update_data.name is not None:
            model.name = update_data.name
        if update_data.is_active is not None:
            model.is_active = update_data.is_active

        updated_model = await self.repository.update(model)

        # find all users with this role
        # invalidate user cache for all users with this role
        users = await self.repository.get_by_role_id(model.id)
        for user in users:
            await invalidate_user_cache(user.id)

        return updated_model

    async def delete(self, role_id: UUID):
        model = await self.get_by_id(role_id)
        user_assignments, api_key_assignments = await self.repository.count_assignments_for_role(
            role_id
        )
        if user_assignments > 0 or api_key_assignments > 0:
            raise AppException(
                error_key=ErrorKey.ROLE_CANNOT_DELETE_IN_USE,
                status_code=409,
            )
        await self.repository.delete(model)
        return {"message": f"Role with ID {role_id} has been deleted."}
