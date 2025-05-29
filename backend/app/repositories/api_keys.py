from uuid import UUID
from fastapi import Depends
<<<<<<< HEAD
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from starlette_context import context
=======
from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.auth.utils import get_current_user_id
from app.cache.redis_cache import make_key_builder
from app.db.models import UserModel
>>>>>>> development
from app.db.models.api_key_role import ApiKeyRoleModel
from app.db.session import get_db
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

from app.db.models.api_key import ApiKeyModel
from app.db.models.role import RoleModel
from app.db.models.role_permission import RolePermissionModel
from app.schemas.api_key import ApiKeyCreate, ApiKeyUpdate
<<<<<<< HEAD


=======
from app.schemas.filter import ApiKeysFilter


api_key_key_builder  = make_key_builder("api_key")

>>>>>>> development
class APiKeysRepository:
    """Repository for user-related database operations."""

    def __init__(self, db: AsyncSession = Depends(get_db)):  # Auto-inject db
        self.db = db

<<<<<<< HEAD
    async def check_exists(self, api_key: str) -> ApiKeyModel:
        query = (select(ApiKeyModel).where(ApiKeyModel.key_val == api_key)
        .options(
                selectinload(ApiKeyModel.user),
=======

    async def get_by_hashed_value(self, hashed_value: str) -> ApiKeyModel:
        query = (select(ApiKeyModel).where(ApiKeyModel.hashed_value == hashed_value)
        .options(
                selectinload(ApiKeyModel.user).selectinload(UserModel.operator),
>>>>>>> development
                selectinload(ApiKeyModel.api_key_roles)
                .selectinload(ApiKeyRoleModel.role)
                .selectinload(RoleModel.role_permissions)
                .selectinload(RolePermissionModel.permission))
        )

        result = await self.db.execute(query)
        return result.scalars().first()



<<<<<<< HEAD
    async def create(self, data: ApiKeyCreate, hashed_api_key: str, masked_value: str) -> ApiKeyModel:
        api_key = await self._get_by_name(data.name)
        if api_key:
            raise AppException(ErrorKey.API_KEY_NAME_EXISTS)

        new_key = ApiKeyModel(name=data.name, is_active=data.is_active, user_id=context["user_id"],
                          created_by=context["user_id"],
                          key_val=hashed_api_key,
                          masked_value=masked_value
                          )
        self.db.add(new_key)
        await self.db.flush()

        for role_id in data.role_ids:
            self.db.add(ApiKeyRoleModel(api_key_id=new_key.id, role_id=role_id, created_by=context["user_id"]))
=======
    async def create(self, api_key_create: ApiKeyCreate, encrypted_api_key: str, hashed_value: str) -> ApiKeyModel:
        api_key = await self._get_by_name(api_key_create.name)
        if api_key:
            raise AppException(ErrorKey.API_KEY_NAME_EXISTS)

        new_key = ApiKeyModel(name=api_key_create.name,
                              is_active=api_key_create.is_active,
                              # Assigned to an agent or to current user if api_key_create.assigned_user_id is none
                              user_id= api_key_create.assigned_user_id if api_key_create.assigned_user_id else get_current_user_id(),
                              key_val=encrypted_api_key,
                              hashed_value=hashed_value,
                              )
        self.db.add(new_key)
        await self.db.flush()

        for role_id in api_key_create.role_ids:
            self.db.add(ApiKeyRoleModel(api_key_id=new_key.id, role_id=role_id))
>>>>>>> development

        await self.db.commit()
        await self.db.refresh(new_key)
        return await self.get_by_id(new_key.id)


    async def get_by_id(self, api_key_id: UUID) -> ApiKeyModel:
        result = await self.db.execute(
                select(ApiKeyModel)
                .where(ApiKeyModel.id == api_key_id)
                .options(selectinload(ApiKeyModel.api_key_roles).selectinload(ApiKeyRoleModel.role))
                )
        return result.scalars().first()

    async def _get_by_name(self, api_key_name: str):
        # Need index
        result = await self.db.execute(
                select(ApiKeyModel)
                .where(ApiKeyModel.name == api_key_name)
                )
        return result.scalars().first()


<<<<<<< HEAD
    async def get_all(self)-> list[ApiKeyModel]:
        result = await self.db.execute(
                select(ApiKeyModel).options(selectinload(ApiKeyModel.api_key_roles).selectinload(ApiKeyRoleModel.role))
                )
=======
    async def get_all(self, api_keys_filter: ApiKeysFilter) -> list[ApiKeyModel]:
        query = (select(ApiKeyModel)
                 .options(selectinload(ApiKeyModel.api_key_roles)
                          .selectinload(ApiKeyRoleModel.role))
                 )
        # Pagination
        query = query.offset(api_keys_filter.skip).limit(api_keys_filter.limit)

        if api_keys_filter.user_id:
            query = query.where(
                    ApiKeyModel.user_id == api_keys_filter.user_id
                    )

        result = await self.db.execute(query)

>>>>>>> development
        return result.scalars().all()


    async def delete(self, api_key: ApiKeyModel):
        await self.db.delete(api_key)
        await self.db.commit()
        return {"message": f"API key {api_key.id} deleted."}


    async def update(self, user_id: UUID, api_key_id: UUID, data: ApiKeyUpdate):
        api_key = await self.get_by_id(api_key_id)
        if not api_key:
            raise AppException(ErrorKey.API_KEY_NOT_FOUND, status_code=404)

        if data.name is not None:
            api_key.name = data.name
        if data.is_active is not None:
            api_key.is_active = data.is_active

        if data.role_ids is not None:
            await self.db.execute(
                    delete(ApiKeyRoleModel)
                    .where(ApiKeyRoleModel.api_key_id == api_key.id)
                    .execution_options(synchronize_session=False)
                    )
            await self.db.flush()  # flush before adding new entries

            for role_id in data.role_ids:
                self.db.add(ApiKeyRoleModel(api_key_id=api_key.id, role_id=role_id))
                
        api_key.updated_by = user_id

        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

