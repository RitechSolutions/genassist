import logging
from typing import Optional
from fastapi import Depends, Request
from app.auth.utils import has_permission, oauth2, api_key_header
from starlette_context import context
from typing import Callable, Awaitable
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.user import UserReadAuth
from app.services.auth import AuthService

logger = logging.getLogger(__name__)


async def get_current_user(request: Request, token: str = Depends(oauth2), api_key: Optional[str] = Depends(
        api_key_header), auth_service: AuthService = Depends()):
    if token is None:
        if api_key is None:
            return None
        api_key_object = await auth_service.authenticate_api_key(api_key)
        if api_key_object is None:
            return None
        request.state.api_key = api_key_object
        #logger.debug("user:"+str(api_key_object.user.id)+" for api key:"+api_key)
        return api_key_object.user

    user = await auth_service.decode_jwt(token)
    return user

# Checks for api key header or user JWT token
async def auth(request: Request, api_key: Optional[str] = Depends(api_key_header),
                     user: Optional[UserReadAuth] = Depends(get_current_user)):
    """
    Authenticates the API key or the JWT Token. If there is a valid authentication then continues.
    """
    if getattr(request.state, "api_key", None):
        # Authenticate API Key if provided
        logger.debug(f"api key {api_key}")

        context["user_id"] = user.id  # store in context
        context["auth_mode"] = "api_key"
        context['user_roles'] = request.state.api_key.roles
        context["operator_id"] = user.operator.id if  user.operator else None
    elif user:
        request.state.user = user  # Attach user to the state
        context["auth_mode"] = "token"
        context["user_id"] = user.id  # store in context
        context['user_roles'] = user.roles
        context["operator_id"] = user.operator.id if user.operator else None  # store in context
    else:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)

def permissions(*permissions: str) -> Callable[[Request], Awaitable[None]]:
    async def wrapper(request: Request):
        if hasattr(request.state, "api_key") and request.state.api_key:
            if not has_permission(request.state.api_key.permissions, *permissions):
                raise AppException(ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)

        elif hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            if not has_permission(user.permissions, *permissions):
               raise AppException(ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)
        else:
            raise AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED)

    return wrapper


