from datetime import datetime
from uuid import UUID
from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.utils import get_password_hash
from app.cache.redis_cache import make_key_builder
from app.core.utils.sql_alchemy_utils import add_dynamic_ordering, add_pagination
from app.db.models import UserRoleModel
from app.db.models.api_key import ApiKeyModel
from app.db.models.api_key_role import ApiKeyRoleModel
from app.db.models.role import RoleModel
from app.db.models.role_permission import RolePermissionModel
from app.db.models.user_type import UserTypeModel
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import delete, select, update

from app.schemas.filter import BaseFilterModel
from app.schemas.user import UserCreate, UserUpdate
from app.db.models.user import UserModel
import logging
from fastapi_cache import FastAPICache

logger = logging.getLogger(__name__)

username_key_builder = make_key_builder("username")
userid_key_builder = make_key_builder("user_id")


@inject
class UserRepository:
    """Repository for user-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user: UserCreate):
        # Validate user type
        user_type = await self.db.get(UserTypeModel, user.user_type_id)

        if not user_type:
            raise AppException(error_key=ErrorKey.USER_TYPE_NOT_FOUND, status_code=404)

        # Create the User instance (without roles yet)
        new_user = UserModel(
            username=user.username,
            hashed_password=user.password,
            email=user.email,
            is_active=user.is_active,
            user_type_id=user.user_type_id,
        )
        self.db.add(new_user)
        await self.db.flush()

        # Create UserRole objects for each role ID
        for role_id in user.role_ids:
            user_role = UserRoleModel(user_id=new_user.id, role_id=role_id)
            self.db.add(user_role)

        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def get(self, user_id: UUID):
        return await self.db.get(UserModel, user_id)

    async def get_full(self, user_id: UUID) -> UserModel | None:
        stmt = (
            select(UserModel)
            .where(UserModel.id == user_id)
            .options(
                # 1) Eager-load the User->UserRole->Role->RolePermission->Permission chain:
                selectinload(UserModel.user_roles)
                .selectinload(UserRoleModel.role)
                .selectinload(RoleModel.role_permissions)
                .selectinload(RolePermissionModel.permission),
                # 2) Eager-load the User->ApiKeys->ApiKeyRole->Role->RolePermission->Permission chain:
                selectinload(UserModel.api_keys)
                .selectinload(ApiKeyModel.api_key_roles)
                .selectinload(ApiKeyRoleModel.role)
                .selectinload(RoleModel.role_permissions)
                .selectinload(RolePermissionModel.permission),
                # 3) Load the user_type relationship:
                joinedload(UserModel.user_type),
                # 4) Load Operator
                joinedload(UserModel.operator),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_username(self, username: str) -> UserModel | None:
        """Retrieve a user by username."""
        query = (
            select(UserModel)
            .where(UserModel.username == username)
            .options(joinedload(UserModel.user_type))
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> UserModel:
        query = select(UserModel).where(UserModel.email == email)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all(self, filter: BaseFilterModel):
        query = select(UserModel).options(
            selectinload(UserModel.user_roles).selectinload(UserRoleModel.role),
            selectinload(UserModel.api_keys)
            .selectinload(ApiKeyModel.api_key_roles)
            .selectinload(ApiKeyRoleModel.role),
            joinedload(UserModel.user_type),
        )
        query = add_dynamic_ordering(UserModel, filter, query)
        query = add_pagination(filter, query)

        results = await self.db.execute(query)
        return results.scalars().all()

    async def update(self, user_id: UUID, data: UserUpdate) -> UserModel:
        user = await self.get(user_id)
        if not user:
            raise AppException(error_key=ErrorKey.USER_NOT_FOUND)

        # Update simple fields
        for field in ["username", "email", "is_active", "notes"]:
            if hasattr(data, field) and getattr(data, field) is not None:
                setattr(user, field, getattr(data, field))

        # Update password (hashed)
        # TODO decide allow update password or do forgot password link
        if data.password:
            user.hashed_password = get_password_hash(data.password)

        # Update user_type
        if data.user_type_id is not None:
            user_type = await self.db.get(UserTypeModel, data.user_type_id)
            if not user_type:
                raise AppException(error_key=ErrorKey.USER_TYPE_NOT_FOUND)
            user.user_type_id = data.user_type_id

        # Update roles
        if data.role_ids is not None:
            await self.db.execute(
                delete(UserRoleModel).where(UserRoleModel.user_id == user.id)
            )
            for role_id in data.role_ids:
                role = await self.db.get(RoleModel, role_id)
                if not role:
                    raise AppException(error_key=ErrorKey.ROLE_NOT_FOUND)
                self.db.add(UserRoleModel(user_id=user.id, role_id=role_id))

        await self.db.commit()
        await self.db.refresh(user)

        # Invalidate the cache for this user
        cache_key = f"auth:users:get_full:{user_id}"
        await FastAPICache.get_backend().clear(key=cache_key)

        return user

    async def update_user_password(
        self, user_id: int, new_hashed: str, next_update_date: datetime
    ):
        stmt = (
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(hashed_password=new_hashed, force_upd_pass_date=next_update_date)
        )
        await self.db.execute(stmt)
        await self.db.commit()
