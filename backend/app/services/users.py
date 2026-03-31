import logging
from uuid import UUID

from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from fastapi_injector import Injected
from injector import inject

from app.auth.utils import get_password_hash
from app.cache.redis_cache import invalidate_user_cache, make_key_builder
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import get_tenant_context
from app.core.utils.date_time_utils import shift_datetime
from app.repositories.users import UserRepository
from app.schemas.filter import BaseFilterModel
from app.schemas.user import UserCreate, UserRead, UserReadAuth, UserUpdate

logger = logging.getLogger(__name__)

userid_key_builder = make_key_builder("user_id")


@inject
class UserService:
    """Handles user-related business logic."""

    def __init__(self, repository: UserRepository = Injected(UserRepository)):
        # repository
        self.repository = repository

    async def create(self, user: UserCreate):
        """Register a user with business logic validation."""
        existing_user = await self.repository.get_by_username(user.username)
        if existing_user:
            raise AppException(error_key=ErrorKey.USERNAME_ALREADY_EXISTS)

        user.password = get_password_hash(user.password)
        new_user = await self.repository.create(user)
        model = await self.repository.get_full(new_user.id)
        return model

    async def get_by_id(self, user_id: UUID) -> UserRead | None:
        """Retrieve a user by ID."""
        user = await self.repository.get_full(user_id)
        if not user:
            return None
        user_auth = UserRead.model_validate(user)
        return user_auth

    @cache(
        expire=300,
        namespace="users:get_by_id_for_auth",
        key_builder=userid_key_builder,
        coder=PickleCoder,
    )
    async def get_by_id_for_auth(self, user_id: UUID) -> UserReadAuth | None:
        """Retrieve a user by ID."""
        tenant_id = get_tenant_context()
        logger.debug(f"get_by_id_for_auth: tenant_id={tenant_id}, user_id={user_id}")
        user = await self.repository.get_full(user_id)
        if not user:
            logger.warning(
                f"User not found: user_id={user_id}, tenant_id={tenant_id}. "
                f"This may indicate the user exists in a different tenant's database."
            )
            return None
        user_auth = UserReadAuth.model_validate(user)
        logger.debug(f"User found: user_id={user_id}, tenant_id={tenant_id}, username={user_auth.username}")
        # if user.user_type.name == 'console':
        #     raise AppException(error_key=ErrorKey.LOGIN_ERROR_CONSOLE_USER)
        return user_auth

    async def get_by_username(self, username: str, throw_not_found: bool = True):
        """Fetch a user by their username."""
        user = await self.repository.get_by_username(username)
        if not user:
            if throw_not_found:
                raise AppException(error_key=ErrorKey.USER_NOT_FOUND, status_code=404)
            return None
        return user

    async def get_user_by_email(self, email: str, throw_not_found: bool = True):
        """Fetch a user by their username."""
        user = await self.repository.get_by_email(email)
        if not user:
            if throw_not_found:
                raise AppException(error_key=ErrorKey.USER_NOT_FOUND, status_code=404)
            return None
        return user

    async def get_all(self, filter: BaseFilterModel):
        """Fetch all users"""
        users = await self.repository.get_all(filter)
        return users

    async def soft_delete(self, user_id: UUID, actor_user_id: UUID | None) -> dict:
        if actor_user_id is not None and user_id == actor_user_id:
            raise AppException(
                error_key=ErrorKey.USER_CANNOT_DELETE_SELF,
                status_code=400,
            )
        deleted = await self.repository.soft_delete(user_id)
        if not deleted:
            raise AppException(error_key=ErrorKey.USER_NOT_FOUND)
        await invalidate_user_cache(user_id)
        return {"message": f"User with ID {user_id} has been deleted."}

    async def restore_soft_deleted(self, user_id: UUID) -> UserRead:
        restored = await self.repository.restore_soft_deleted(user_id)
        if not restored:
            raise AppException(error_key=ErrorKey.USER_NOT_FOUND)
        await invalidate_user_cache(user_id)
        full = await self.get_by_id(user_id)
        if not full:
            raise AppException(error_key=ErrorKey.USER_NOT_FOUND)
        return full

    async def update(self, user_id: UUID, user_data: UserUpdate):
        updated_user = await self.repository.update(user_id, user_data)
        await invalidate_user_cache(user_id)
        user_with_full_data = await self.get_by_id(updated_user.id)
        return user_with_full_data

    async def update_user_password(self, user_id, new_hashed):
        updated_user = await self.repository.update_user_password(
            user_id, new_hashed, shift_datetime(unit="months", amount=3)
        )
        await invalidate_user_cache(user_id)
        return updated_user
