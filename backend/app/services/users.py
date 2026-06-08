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

        existing_email = await self.repository.get_by_email(
            user.email, include_deleted=True
        )
        if existing_email:
            raise AppException(error_key=ErrorKey.EMAIL_ALREADY_EXISTS)

        if user.entra_oid:
            existing_oid = await self.repository.get_by_entra_oid(user.entra_oid)
            if existing_oid is not None:
                raise AppException(error_key=ErrorKey.ENTRA_OID_IN_USE, status_code=409)

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
        logger.debug("User found: user_id=%s, tenant_id=%s", user_id, tenant_id)
        # if user.user_type.name == 'console':
        #     raise AppException(error_key=ErrorKey.LOGIN_ERROR_CONSOLE_USER)
        return user_auth

    async def get_by_username(self, username: str, *, include_deleted: bool = False, throw_not_found: bool = True):
        """Fetch a user by their username."""
        user = await self.repository.get_by_username(username, include_deleted=include_deleted)
        if not user:
            if throw_not_found:
                raise AppException(error_key=ErrorKey.USER_NOT_FOUND, status_code=404)
            return None
        return user

    async def get_by_email(self, email: str, *, include_deleted: bool = False, throw_not_found: bool = True):
        """Fetch a user by their email."""
        user = await self.repository.get_by_email(email, include_deleted=include_deleted)
        if not user:
            if throw_not_found:
                raise AppException(error_key=ErrorKey.USER_NOT_FOUND, status_code=404)
            return None
        return user

    async def get_by_username_or_email(self, username_or_email: str, *, include_deleted: bool = False, throw_not_found: bool = True):
        """Fetch a user by their username."""
        user = await self.repository.get_by_username_or_email(username_or_email, include_deleted=include_deleted)
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
        if user_data.role_ids is not None and len(user_data.role_ids) == 0:
            raise AppException(error_key=ErrorKey.USER_ROLES_REQUIRED, status_code=400)

        if user_data.email is not None:
            existing = await self.repository.get_by_email(
                user_data.email, include_deleted=True
            )
            if existing is not None and existing.id != user_id:
                raise AppException(error_key=ErrorKey.EMAIL_ALREADY_EXISTS)

        if "entra_oid" in user_data.model_fields_set and user_data.entra_oid:
            existing_oid = await self.repository.get_by_entra_oid(user_data.entra_oid)
            if existing_oid is not None and existing_oid.id != user_id:
                raise AppException(error_key=ErrorKey.ENTRA_OID_IN_USE, status_code=409)

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

    def _ensure_active_non_console_for_sso(self, user) -> None:
        if not getattr(user, "is_active", None):
            raise AppException(error_key=ErrorKey.INVALID_USER, status_code=401)
        ut = getattr(user, "user_type", None)
        if ut and ut.name == "console":
            raise AppException(error_key=ErrorKey.INVALID_USER_CONSOLE, status_code=401)

    async def _allocate_unique_sso_username(self) -> str:
        import secrets

        for _ in range(24):
            candidate = secrets.token_hex(4)
            existing = await self.repository.get_by_username(candidate)
            if not existing:
                return candidate
        raise AppException(error_key=ErrorKey.INTERNAL_SERVER_ERROR, status_code=500)

    async def resolve_user_for_microsoft_sso(self, *, entra_oid: str, email: str | None):
        from uuid import UUID as PyUUID

        from app.core.config.settings import settings

        user = await self.repository.get_by_entra_oid(entra_oid)
        if user:
            self._ensure_active_non_console_for_sso(user)
            return user

        if email:
            by_email = await self.repository.get_by_email(email, include_deleted=False)
            if by_email:
                if by_email.entra_oid and by_email.entra_oid != entra_oid:
                    raise AppException(
                        error_key=ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
                        status_code=403,
                        error_detail="This email is already linked to another Microsoft account.",
                    )
                if not by_email.entra_oid:
                    await self.repository.set_entra_oid_if_empty(by_email.id, entra_oid)
                user = await self.repository.get_full(by_email.id)
                if not user:
                    raise AppException(error_key=ErrorKey.USER_NOT_FOUND, status_code=404)
                self._ensure_active_non_console_for_sso(user)
                return user

        if not settings.SSO_MICROSOFT_AUTO_PROVISION:
            raise AppException(error_key=ErrorKey.SSO_MICROSOFT_USER_DENIED, status_code=403)

        if not settings.SSO_MICROSOFT_DEFAULT_USER_TYPE_ID or not settings.SSO_MICROSOFT_DEFAULT_ROLE_IDS:
            raise AppException(error_key=ErrorKey.SSO_MICROSOFT_NOT_CONFIGURED, status_code=500)

        if not email:
            raise AppException(error_key=ErrorKey.SSO_MICROSOFT_USER_DENIED, status_code=403)

        role_ids = [
            PyUUID(x.strip())
            for x in settings.SSO_MICROSOFT_DEFAULT_ROLE_IDS.split(",")
            if x.strip()
        ]
        user_type_id = PyUUID(settings.SSO_MICROSOFT_DEFAULT_USER_TYPE_ID.strip())
        import secrets

        pwd = get_password_hash(secrets.token_urlsafe(16)[:20])
        username = await self._allocate_unique_sso_username()
        try:
            user = await self.repository.create_from_microsoft_sso(
                username=username,
                email=email,
                hashed_password=pwd,
                user_type_id=user_type_id,
                role_ids=role_ids,
                entra_oid=entra_oid,
            )
        except AppException as e:
            if e.error_key == ErrorKey.SSO_MICROSOFT_OAUTH_ERROR:
                raise AppException(
                    error_key=ErrorKey.SSO_MICROSOFT_USER_DENIED,
                    status_code=403,
                    error_detail="Could not create your GenAssist profile (duplicate email or username).",
                ) from e
            raise
        await invalidate_user_cache(user.id)
        self._ensure_active_non_console_for_sso(user)
        return user
