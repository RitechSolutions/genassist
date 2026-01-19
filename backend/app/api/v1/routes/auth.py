import logging
from typing import Optional
from typing import Annotated
from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_injector import Injected

from app.auth.dependencies import auth, get_current_user
from app.auth.utils import get_password_hash
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.config.settings import settings
from app.middlewares.rate_limit_middleware import limiter
from app.schemas.password_update_request import PasswordUpdateRequest
from app.services.auth import AuthService
from app.services.users import UserService

from app.core.tenant_scope import get_tenant_context
from app.auth.jwt_dependencies import validate_api_key, encode_jwt, decode_jwt
from datetime import datetime, timedelta, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/token", summary="Authenticate user and return access and refresh tokens")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_HOUR}/hour")
async def auth_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Injected(AuthService),
):
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    token_data = {"sub": user.username, "user_id": str(user.id)}
    access_token = auth_service.create_access_token(data=token_data)
    refresh_token = auth_service.create_refresh_token(data=token_data)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "force_upd_pass_date": user.force_upd_pass_date,
    }


@router.post(
    "/refresh_token", summary="Refresh user access token via provided refresh token"
)
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
async def refresh_token(
    request: Request,
    refresh_token: Annotated[str, Form(...)],
    auth_service: AuthService = Injected(AuthService),
):
    user = await auth_service.decode_jwt(refresh_token)  # Decode user
    access_token = auth_service.create_access_token(
        data={"sub": user.username, "user_id": str(user.id)}
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", summary="Returns current user details", dependencies=[Depends(auth)])
async def me(
    user: Optional[dict] = Depends(get_current_user),
    user_service: UserService = Injected(UserService),
):

    if user:
        user_details = await user_service.get_by_id_for_auth(
            user.id
        )  # Get user details from database
        permissions = user_details.permissions
        return {
            "id": user_details.id,
            "username": user_details.username,
            "email": user_details.email,
            "permissions": permissions,
            "force_upd_pass_date": user.force_upd_pass_date,
        }  # Return user details
    else:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)


@router.post("/change-password", summary="Change password using old password")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
async def change_password(
    request: Request,
    req: PasswordUpdateRequest,
    auth_service: AuthService = Injected(AuthService),
    user_service: UserService = Injected(UserService),
):
    # Authenticate user
    user = await auth_service.authenticate_user(req.username, req.old_password)

    new_hashed = get_password_hash(req.new_password)

    await user_service.update_user_password(user.id, new_hashed)

    return {"message": "Password changed successfully"}




@router.post("/plugin-stst", summary="Issue short-lived chat token")
async def plugin_stst(
    api_key: str = Depends(validate_api_key)
):
    
    tenant_id = get_tenant_context()

    payload = {
        "sub": str(uuid4()),
        "scope": "chat",
        "aud": "conversation-api",
        "api_key": api_key,
        "tenant_id": tenant_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }

    token = encode_jwt(payload)
    return {"sts_token": token, "token_type": "bearer"}