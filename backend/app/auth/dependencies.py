import logging
from urllib.parse import parse_qs
from fastapi import WebSocket, status
from starlette_context import context
from typing import Callable, Awaitable
from jose import ExpiredSignatureError, JWTError
from typing import Optional
from fastapi import Depends, Query, Request, WebSocketException
from fastapi_injector import Injected
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.auth.utils import has_permission, oauth2, api_key_header
from app.schemas.socket_principal import SocketPrincipal
from app.schemas.user import UserReadAuth
from app.services.auth import AuthService
from app.core.config.settings import settings
from app.core.tenant_scope import set_tenant_context

logger = logging.getLogger(__name__)


async def get_current_user(request: Request, token: str = Depends(oauth2), api_key: Optional[str] = Depends(
        api_key_header), auth_service: AuthService = Injected(AuthService)):
    if token is None:
        if api_key is None:
            return None
        api_key_object = await auth_service.authenticate_api_key(api_key)
        if api_key_object is None:
            return None
        request.state.api_key = api_key_object
        # logger.debug("user:"+str(api_key_object.user.id)+" for api key:"+api_key)
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

        context["user_id"] = user.id if user else None  # store in context
        context["auth_mode"] = "api_key"
        context['user_roles'] = request.state.api_key.roles
        context["operator_id"] = user.operator.id if user and user.operator else None
    elif user:
        request.state.user = user  # Attach user to the state
        context["auth_mode"] = "token"
        context["user_id"] = user.id  # store in context
        context['user_roles'] = user.roles
        # store in context
        context["operator_id"] = user.operator.id if user.operator else None
    else:
        raise AppException(
            status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)


def permissions(*permissions: str) -> Callable[[Request], Awaitable[None]]:
    async def wrapper(request: Request):
        if hasattr(request.state, "api_key") and request.state.api_key:
            if not has_permission(request.state.api_key.permissions, *permissions):
                raise AppException(
                    ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)

        elif hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            if not has_permission(user.permissions, *permissions):
                raise AppException(
                    ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)
        else:
            raise AppException(
                status_code=403, error_key=ErrorKey.NOT_AUTHORIZED)

    return wrapper


def socket_auth(required_permissions: list[str]):
    """
    Returns a *dependency function* that:
      • authenticates via JWT or API key
      • verifies `required_permission`
      • closes the socket on auth failures
      • returns a SocketPrincipal on success
    """

    async def _auth_dependency(
        websocket: WebSocket,
        access_token: str | None = Query(default=None),
        api_key: str | None = Query(default=None),
        auth_service=Injected(AuthService),
    ) -> SocketPrincipal:
        try:
            # Extract tenant information from WebSocket (priority: query param > header > subdomain)
            resolved_tenant_id = None
            tenant_slug = None
            
            # lowercase the tenant header name to make the check case-insensitive
            tenant_header_name = settings.TENANT_HEADER_NAME.lower()

            if settings.MULTI_TENANT_ENABLED:
                # Method 1: Extract from query parameter (highest priority)
                # Check both the header name as query param and also try direct query string parsing
                query_params = {}
                if websocket.url.query:
                    query_params = parse_qs(websocket.url.query)
                    # parse_qs returns lists, so get first item if exists
                    tenant_query_param = (
                        query_params.get(tenant_header_name, [None])[0] or
                        query_params.get("tenant_id", [None])[0] or
                        query_params.get("tenant", [None])[0]
                    )
                    if tenant_query_param:
                        tenant_slug = tenant_query_param
                        resolved_tenant_id = tenant_slug
                        logger.debug(f"WebSocket tenant resolved from query parameter: {tenant_slug}")

                # Method 2: Extract from header (only if not found in query)
                if not resolved_tenant_id and tenant_header_name in websocket.headers:
                    tenant_slug = websocket.headers[tenant_header_name]
                    resolved_tenant_id = tenant_slug
                    logger.debug(f"WebSocket tenant resolved from header: {tenant_slug}")

                # Method 3: Extract from subdomain (if enabled, only if not found above)
                if not resolved_tenant_id and settings.TENANT_SUBDOMAIN_ENABLED:
                    host = websocket.headers.get("host", "")
                    if "." in host:
                        subdomain = host.split(".")[0]
                        if subdomain and subdomain != "www":
                            tenant_slug = subdomain
                            resolved_tenant_id = tenant_slug
                            logger.debug(f"WebSocket tenant resolved from subdomain: {tenant_slug}")

            resolved_tenant_id = resolved_tenant_id or "master"
            # Set tenant context for dependency injection during WebSocket session
            set_tenant_context(resolved_tenant_id)
            logger.debug(f"WebSocket tenant context set: {resolved_tenant_id}")

            if access_token:
                user = await auth_service.decode_jwt(access_token)
                principal, user_id, perms = user, user.id, user.permissions
            elif api_key:
                key_obj = await auth_service.authenticate_api_key(api_key)
                principal, user_id, perms = key_obj, key_obj.user.id, key_obj.permissions
            else:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION, reason="Missing credentials")

            if not set(required_permissions).issubset(set(perms)):
                raise WebSocketException(
                    code=4403, reason="Invalid permissions")

            return SocketPrincipal(principal, user_id, perms, resolved_tenant_id)

        except ExpiredSignatureError:
            raise WebSocketException(code=4401, reason="Token expired")
        except JWTError:
            raise WebSocketException(code=4401, reason="Invalid token")

    return Depends(_auth_dependency)
