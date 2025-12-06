import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from injector import inject
from jose import ExpiredSignatureError, JWTError, jwt
from app.auth.utils import verify_password
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.api_key import ApiKeyModel
from app.schemas.api_key import ApiKeyInternal
from app.schemas.user import UserReadAuth
from app.services.api_keys import ApiKeysService
from app.services.users import UserService



logger = logging.getLogger(__name__)

@inject
class AuthService:
    def __init__(self, user_service: UserService, api_keys_service: ApiKeysService):
        self.user_service = user_service
        self.api_keys_service = api_keys_service
        self.secret_key = os.environ.get("JWT_SECRET_KEY")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60
        self.refresh_token_expire_days = 2


    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        try:
            to_encode = data.copy()
            expire = datetime.now() + (expires_delta or timedelta(minutes=self.access_token_expire_minutes))
            to_encode.update({"exp": expire})
            return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        except Exception as error:
            raise AppException(error_key=ErrorKey.ERROR_CREATE_TOKEN,
                               error_detail="Error while creating access token", error_obj=error, status_code=401)


    def create_refresh_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.now() + (expires_delta or timedelta(days=self.refresh_token_expire_days))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)


    async def decode_jwt(self, token: str) -> UserReadAuth:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username = payload.get("sub")
            user_id = payload.get("user_id")

            if username is None or user_id is None:
                raise AppException(status_code=401, error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                                   error_detail="JWT error: Username is None")
            user: UserReadAuth | None  =  await self.user_service.get_by_id_for_auth(user_id)

            if user is None or not user.is_active:
                raise AppException(error_key=ErrorKey.INVALID_USER, status_code=401)
            # I not set there is no expiry
            if user.force_upd_pass_date and user.force_upd_pass_date < datetime.now(timezone.utc):
                raise AppException(error_key=ErrorKey.FORCE_PASSWORD_UPDATE, status_code=401)

            return user
        except ExpiredSignatureError as error:
            raise AppException(status_code=401, error_key=ErrorKey.EXPIRED_TOKEN,
                               error_detail=f"Expired token: {error}")
        except JWTError as error:
            raise AppException(status_code=401, error_key=ErrorKey.COULD_NOT_VALIDATE_CREDENTIALS,
                               error_detail=f"JWT error: {error}", error_obj=error)


    async def authenticate_api_key(self, api_key: str) -> ApiKeyInternal:
        """Authenticate and return API key object if valid."""
        api_key = await self.api_keys_service.validate_and_get_api_key(api_key)
        if api_key.user.force_upd_pass_date and api_key.user.force_upd_pass_date < datetime.now(timezone.utc):
            raise AppException(error_key=ErrorKey.FORCE_PASSWORD_UPDATE, status_code=401)
        return api_key


    async def authenticate_user(self, username_or_email: str, password: str):
        """Authenticate user by username or email and password."""
        user = await self.user_service.get_by_username(username_or_email, throw_not_found=False)
        # Check by email if not found by username
        if not user:
            user = await self.user_service.get_user_by_email(username_or_email, throw_not_found=False)

        if not user:
            raise AppException(error_key=ErrorKey.INVALID_USERNAME_OR_PASSWORD, status_code=401,
                               error_detail="Username not found.")

        if not user.is_active:
            raise AppException(error_key=ErrorKey.INVALID_USER, status_code=401)

        if user.user_type.name == "console":
            raise AppException(error_key=ErrorKey.INVALID_USER_CONSOLE, status_code=401)

        if not verify_password(password, user.hashed_password):
            raise AppException(error_key=ErrorKey.INVALID_USERNAME_OR_PASSWORD, status_code=401,
                               error_detail="Incorrect password.")

        return user