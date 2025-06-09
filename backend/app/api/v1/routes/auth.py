import logging
from typing import Optional
from typing import Annotated
from fastapi import APIRouter, Depends, Form
from fastapi.security import OAuth2PasswordRequestForm
from app.auth.dependencies import auth, get_current_user
from app.auth.utils import get_password_hash
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.password_update_request import PasswordUpdateRequest
from app.schemas.user import UserReadAuth
from app.services.auth import AuthService
from app.services.users import UserService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/token", summary="Authenticate user and return access and refresh tokens")
async def auth_token(form_data: OAuth2PasswordRequestForm = Depends(), auth_service: AuthService = Depends()):
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    token_data = {"sub": user.username, "user_id": str(user.id)}
    access_token = auth_service.create_access_token(data=token_data)
    refresh_token = auth_service.create_refresh_token(data=token_data)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer",
            "force_upd_pass_date": user.force_upd_pass_date}

@router.post("/refresh_token", summary="Refresh user access token via provided refresh token")
async def refresh_token(refresh_token: Annotated[str, Form(...)], auth_service: AuthService =  Depends()):
    user = await auth_service.decode_jwt(refresh_token)  # Decode user
    access_token = auth_service.create_access_token(data={"sub": user.username, "user_id": str(user.id)})

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", summary="Returns current user details", dependencies=[Depends(auth)])
async def me(user: Optional[dict] = Depends(get_current_user),
             user_service: UserService = Depends()):
    
    if user:
        user_details = await user_service.get_by_id_for_auth(user.id)  # Get user details from database
        permissions = user_details.permissions
        return {"id": user_details.id, "username": user_details.username, "email": user_details.email, "permissions":
            permissions, "force_upd_pass_date": user.force_upd_pass_date}  # Return user details
    else:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)


@router.post("/change-password", summary="Change password using old password")
async def change_password(
    req: PasswordUpdateRequest,
    auth_service: AuthService = Depends(),
    user_service: UserService = Depends()
):
    # Authenticate user
    user = await auth_service.authenticate_user(req.username, req.old_password)

    new_hashed = get_password_hash(req.new_password)

    await user_service.update_user_password(user.id, new_hashed)

    return {"message": "Password changed successfully"}