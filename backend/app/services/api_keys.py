import logging
from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from injector import inject
from starlette_context import context
from uuid import UUID
from fastapi import Depends
from app.auth.utils import (
    current_user_is_admin,
    generate_api_key,
    hash_api_key,
    is_current_user_supervisor_or_admin,
)
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from app.db.models import ApiKeyModel
from app.repositories.roles import RolesRepository
from app.schemas.api_key import ApiKeyCreate, ApiKeyInternal, ApiKeyUpdate
from app.repositories.api_keys import ApiKeysRepository, api_key_key_builder
from app.schemas.filter import ApiKeysFilter
from app.schemas.role import RoleRead
from cryptography.fernet import InvalidToken


logger = logging.getLogger(__name__)


@inject
class ApiKeysService:
    def __init__(
        self,
        repository: ApiKeysRepository,
        roles_repository: RolesRepository,
    ):
        self.repository = repository
        self.roles_repository = roles_repository

    @cache(
        expire=300,
        namespace="api_keys:validate_and_get_api_key",
        key_builder=api_key_key_builder,
        coder=PickleCoder,
    )
    async def validate_and_get_api_key(self, api_key: str) -> ApiKeyInternal:
        hashed_value = hash_api_key(api_key)
        logger.debug("getting api key for hashed val:" + hashed_value)
        api_key_model: ApiKeyModel = await self.repository.get_by_hashed_value(
            hash_api_key(api_key)
        )
        if not api_key_model:
            raise AppException(status_code=401, error_key=ErrorKey.INVALID_API_KEY)
        api_key_read = ApiKeyInternal.model_validate(api_key_model)
        return api_key_read

    async def create(self, data: ApiKeyCreate):
        """
        Creates a new API key for the user, ensuring that the user can only
        assign roles they actually possess.
        """
        # Validate that the requested role_ids are a subset of the user's own roles.
        user_roles = context["user_roles"]
        self._validate_role_ids(user_roles, data.role_ids)

        if data.agent_id:
            agent_role = await self.roles_repository.get_by_name("ai agent")
            data.role_ids = [agent_role.id]

        generated_api_key = generate_api_key()
        encrypted_api_key = encrypt_key(generated_api_key)
        hashed_value = hash_api_key(generated_api_key)

        api_key_pyd_model = await self.repository.create(
            data, encrypted_api_key, hashed_value
        )

        # Build the pydantic return object, including the 'key_val'
        api_key_pyd_model.key_val = generated_api_key
        return api_key_pyd_model

    async def get(self, api_key_id: UUID):
        api_key = await self.repository.get_by_id(api_key_id)
        if not api_key:
            raise AppException(error_key=ErrorKey.API_KEY_NOT_FOUND, status_code=404)
        try:
            api_key.key_val = decrypt_key(api_key.key_val)
        except InvalidToken:
            raise AppException(
                error_key=ErrorKey.INVALID_API_KEY_ENCRYPTION, status_code=500
            )
        return api_key

    async def get_all(self, api_key_filter: ApiKeysFilter):
        api_keys = await self.repository.get_all(api_key_filter)
        for api_key in api_keys:
            try:
                api_key.key_val = decrypt_key(api_key.key_val)
            except InvalidToken:
                raise AppException(
                    error_key=ErrorKey.INVALID_API_KEY_ENCRYPTION, status_code=500
                )
        return api_keys

    async def delete(self, api_key_id: UUID):
        api_key = await self.repository.get_by_id(api_key_id)
        if not api_key:
            raise AppException(error_key=ErrorKey.API_KEY_NOT_FOUND, status_code=404)
        return await self.repository.soft_delete(api_key)

    async def update(self, api_key_id: UUID, data: ApiKeyUpdate):
        """
        Patch/Update an existing API key's fields, again checking roles if user wants to update role_ids.
        """

        # If the user wants to update role_ids, we must validate them:
        if data.role_ids is not None:
            self._validate_role_ids(context["user_roles"], data.role_ids)

        model = await self.repository.update(context["user_id"], api_key_id, data)
        return model

    def _validate_role_ids(
        self, user_roles: list[RoleRead], requested_role_ids: list[UUID]
    ) -> None:
        """
        Ensures the user only assigns roles that they already possess.
        If the user doesn't have the role, raise an authorization error.
        """
        if not requested_role_ids:
            return  # No roles requested, nothing to validate

        # if current user is admin allow any role to assign
        if current_user_is_admin():
            return

        # Gather the role IDs that the user actually possesses
        active_role_ids = {ur.id for ur in user_roles if ur.is_active}

        # If user doesn't have any roles, or we see a mismatch, raise an exception
        for rid in requested_role_ids:
            if rid not in active_role_ids:
                raise AppException(
                    error_key=ErrorKey.ROLE_NOT_ALLOWED,
                    status_code=403,
                )
