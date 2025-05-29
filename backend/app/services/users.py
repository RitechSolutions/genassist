from uuid import UUID
from fastapi import Depends
<<<<<<< HEAD

from app.auth.utils import get_password_hash
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.users import UserRepository
from app.schemas.user import UserCreate, UserUpdate
=======
from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from app.auth.utils import get_password_hash
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.users import UserRepository, userid_key_builder
from app.schemas.user import UserCreate, UserRead, UserReadAuth, UserUpdate
>>>>>>> development

class UserService:
    """Handles user-related business logic."""

    def __init__(self, repository: UserRepository = Depends()):  # Auto-inject
        # repository
        self.repository = repository

    async def create(self, user: UserCreate):
        """Register a user with business logic validation."""
        existing_user = await self.repository.get_by_username(user.username)
        if existing_user:
<<<<<<< HEAD
            raise AppException(error_key=ErrorKey.USERNAME_ALREADY_EXISTS)  # Handle duplicate username
=======
            raise AppException(error_key=ErrorKey.USERNAME_ALREADY_EXISTS)
>>>>>>> development

        user.password = get_password_hash(user.password)
        new_user =  await self.repository.create(user)
        model = await self.repository.get_full(new_user.id)
        return model

<<<<<<< HEAD
    async def get_by_id(self, user_id: UUID):
=======
    async def get_by_id(self, user_id: UUID) -> UserRead | None:
>>>>>>> development
        """Retrieve a user by ID."""
        user = await self.repository.get_full(user_id)
        if not user:
            return None
<<<<<<< HEAD
        return user
=======
        user_auth = UserRead.model_validate(user)
        return user_auth

    @cache(
            expire=300,
            namespace="users:get_by_id_for_auth",
            key_builder=userid_key_builder,
            coder=PickleCoder
            )
    async def get_by_id_for_auth(self, user_id: UUID) -> UserReadAuth | None:
        """Retrieve a user by ID."""
        user = await self.repository.get_full(user_id)
        if not user:
            return None
        user_auth = UserReadAuth.model_validate(user)
        if user.user_type.name == 'console':
            raise AppException(error_key=ErrorKey.LOGIN_ERROR_CONSOLE_USER)
        return user_auth
>>>>>>> development

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

    async def get_all(self):
        """Fetch all users"""
        users = await self.repository.get_all()
        return users

    async def update(self, user_id: UUID, user_data: UserUpdate):
        updated_user =  await self.repository.update(user_id, user_data)
        user_with_full_data = await self.get_by_id(updated_user.id)
        return user_with_full_data
