from uuid import UUID
from fastapi import Depends
from fastapi_injector import Injected
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.user_types import UserTypesRepository
from app.schemas.user import UserTypeCreate, UserTypeUpdate

@inject
class UserTypesService:
    """Handles user-types-related business logic."""

    def __init__(self, repository: UserTypesRepository = Injected(UserTypesRepository)):  # Auto-inject
        self.repository = repository

    async def create(self, user_type: UserTypeCreate):

        model = await self.repository.create(user_type)
        return model

    async def get_by_id(self, user_type_id: UUID):
        """Retrieve a user by ID."""
        model = await self.repository.get_by_id(user_type_id)
        if not model:
            raise AppException(error_key=ErrorKey.USER_TYPE_NOT_FOUND, status_code=404)
        return model

    async def get_all(self):
        models = await self.repository.get_all()
        return models

    async def update(self, user_type_id: UUID, update_data: UserTypeUpdate):
        """Update an existing user_type"""
        model = await self.repository.get_by_id(user_type_id)
        if not model:
            raise AppException(error_key=ErrorKey.USER_TYPE_NOT_FOUND, status_code=404)
        model.name = update_data.name
        await self.repository.update(model)
        return model

    async def delete(self, user_type_id: UUID):
        """Delete an existing user_type"""
        model = await self.repository.get_by_id(user_type_id)
        if not model:
            raise AppException(error_key=ErrorKey.USER_TYPE_NOT_FOUND, status_code=404)
        await self.repository.delete(model)
        return {"message": f"UserRead type with ID {user_type_id} has been deleted."}

    async def update_partial(self, user_type_id: UUID, update_data: UserTypeUpdate):
        """Partially update a user_type"""
        model = await self.repository.get_by_id(user_type_id)
        if not model:
            raise AppException(error_key=ErrorKey.USER_TYPE_NOT_FOUND, status_code=404)

        if update_data.name is not None:
            model.name = update_data.name

        await self.repository.update(model)
        return model
