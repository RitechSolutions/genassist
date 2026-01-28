import logging
from urllib.parse import parse_qs
from uuid import UUID
from fastapi import WebSocket, status
from starlette_context import context
from typing import Callable, Awaitable
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
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


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2),
    api_key: Optional[str] = Depends(api_key_header),
    auth_service: AuthService = Injected(AuthService),
):
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


async def auth(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    user: Optional[UserReadAuth] = Depends(get_current_user),
):
    """
    Authenticates the API key or the JWT Token. If there is a valid authentication then continues.
    """
    if getattr(request.state, "api_key", None):
        # Authenticate API Key if provided
        logger.debug(f"api key {api_key}")

        context["user_id"] = user.id if user else None  # store in context
        context["auth_mode"] = "api_key"
        context["user_roles"] = request.state.api_key.roles
        context["operator_id"] = user.operator.id if user and user.operator else None
    elif user:
        request.state.user = user  # Attach user to the state
        context["auth_mode"] = "token"
        context["user_id"] = user.id  # store in context
        context["user_roles"] = user.roles
        # store in context
        context["operator_id"] = user.operator.id if user.operator else None
    else:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)


def permissions(*permissions: str) -> Callable[[Request], Awaitable[None]]:
    async def wrapper(request: Request):
        # Check for guest token first
        if hasattr(request.state, "guest_token") and request.state.guest_token:
            guest_permissions = request.state.guest_token.get("permissions", [])
            if not has_permission(guest_permissions, *permissions):
                raise AppException(
                    ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403
                )
            return

        if hasattr(request.state, "api_key") and request.state.api_key:
            if not has_permission(request.state.api_key.permissions, *permissions):
                raise AppException(
                    ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403
                )

        elif hasattr(request.state, "user") and request.state.user:
            user = request.state.user
            if not has_permission(user.permissions, *permissions):
                raise AppException(
                    ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403
                )
        else:
            raise AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED)

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
                        logger.debug(
                            f"WebSocket tenant resolved from query parameter: {tenant_slug}"
                        )

                # Method 2: Extract from header (only if not found in query)
                if not resolved_tenant_id and tenant_header_name in websocket.headers:
                    tenant_slug = websocket.headers[tenant_header_name]
                    resolved_tenant_id = tenant_slug
                    logger.debug(
                        f"WebSocket tenant resolved from header: {tenant_slug}"
                    )

                # Method 3: Extract from subdomain (if enabled, only if not found above)
                if not resolved_tenant_id and settings.TENANT_SUBDOMAIN_ENABLED:
                    host = websocket.headers.get("host", "")
                    if "." in host:
                        subdomain = host.split(".")[0]
                        if subdomain and subdomain != "www":
                            tenant_slug = subdomain
                            resolved_tenant_id = tenant_slug
                            logger.debug(
                                f"WebSocket tenant resolved from subdomain: {tenant_slug}"
                            )

            resolved_tenant_id = resolved_tenant_id or "master"
            # Set tenant context for dependency injection during WebSocket session
            set_tenant_context(resolved_tenant_id)
            logger.debug(f"WebSocket tenant context set: {resolved_tenant_id}")

            if access_token:
                user = await auth_service.decode_jwt(access_token)
                principal, user_id, perms = user, user.id, user.permissions
            elif api_key:
                key_obj = await auth_service.authenticate_api_key(api_key)
                principal, user_id, perms = (
                    key_obj,
                    key_obj.user.id,
                    key_obj.permissions,
                )
            else:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION, reason="Missing credentials"
                )

            if not set(required_permissions).issubset(set(perms)):
                raise WebSocketException(code=4403, reason="Invalid permissions")

            return SocketPrincipal(principal, user_id, perms, resolved_tenant_id)

        except ExpiredSignatureError:
            raise WebSocketException(code=4401, reason="Token expired")
        except InvalidTokenError:
            raise WebSocketException(code=4401, reason="Invalid token")

    return Depends(_auth_dependency)


async def _get_conversation_with_agent(conversation_id: UUID):
    """
    Fetch conversation with operator and agent relationships loaded in a single query.
    Returns (conversation, agent) tuple, or (None, None) if not found.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from app.db.models import ConversationModel, OperatorModel, AgentModel
    from app.dependencies.injector import injector
    from app.repositories.conversations import ConversationRepository

    conversation_repo = injector.get(ConversationRepository)

    # Single query with eager loading of operator, agent, and agent.security_settings
    query = (
        select(ConversationModel)
        .where(ConversationModel.id == conversation_id)
        .options(
            joinedload(ConversationModel.operator)
            .joinedload(OperatorModel.agent)
            .joinedload(AgentModel.security_settings)
        )
    )

    result = await conversation_repo.db.execute(query)
    conversation = result.unique().scalars().first()

    if not conversation or not conversation.operator or not conversation.operator.agent:
        return None, None

    return conversation, conversation.operator.agent


async def _handle_guest_token(
    request: Request,
    token_str: str,
    conversation_id: UUID,
    auth_service: AuthService,
    agent,
) -> bool:
    """
    Handle guest token authentication.
    Returns True if guest token was successfully processed, False otherwise.
    """
    try:
        guest_token_data = await auth_service.decode_guest_token(token_str)

        # Validate token is for this conversation
        if guest_token_data["conversation_id"] != str(conversation_id):
            raise AppException(
                status_code=403,
                error_key=ErrorKey.NOT_AUTHORIZED,
                error_detail="Token is not valid for this conversation",
            )

        # Extract and convert user_id
        guest_user_id = guest_token_data.get("user_id")
        user_id_uuid = (
            UUID(guest_user_id)
            if guest_user_id and isinstance(guest_user_id, str)
            else guest_user_id
        )

        # Set context for guest token
        request.state.guest_token = guest_token_data
        request.state.user = None
        context["auth_mode"] = "guest_token"
        context["user_id"] = user_id_uuid
        context["user_roles"] = []
        context["operator_id"] = agent.operator.id if agent.operator else None

        return True
    except AppException as e:
        # Re-raise guest token validation errors
        if (
            "guest token" in str(e.error_detail).lower()
            or "conversation" in str(e.error_detail).lower()
        ):
            raise
        # Not a guest token, return False to continue with regular auth
        return False


async def _handle_authenticated_agent(
    request: Request,
    conversation_id: UUID,
    agent,
    api_key: Optional[str],
    user: Optional[UserReadAuth],
    auth_service: AuthService,
):
    """Handle authentication when agent.security_settings.token_based_auth is true (JWT only)."""
    # Reject API keys for token_based_auth agents
    if getattr(request.state, "api_key", None):
        raise AppException(
            status_code=403,
            error_key=ErrorKey.NOT_AUTHORIZED,
            error_detail="This agent requires JWT token authentication. API keys are not allowed.",
        )

    # Try guest token first
    try:
        token_str = await oauth2(request)
        if token_str and await _handle_guest_token(
            request, token_str, conversation_id, auth_service, agent
        ):
            return
    except (AppException, Exception):
        # If oauth2 fails or guest token handling fails, continue to regular JWT
        pass

    # Regular JWT token authentication
    if not user:
        raise AppException(
            status_code=401,
            error_key=ErrorKey.NOT_AUTHENTICATED,
            error_detail="JWT token required for token_based_auth agents",
        )

    request.state.user = user
    context["auth_mode"] = "token"
    context["user_id"] = user.id
    context["user_roles"] = user.roles
    context["operator_id"] = user.operator.id if user.operator else None


async def auth_for_conversation_update(
    request: Request,
    conversation_id: UUID,
    api_key: Optional[str] = Depends(api_key_header),
    user: Optional[UserReadAuth] = Depends(get_current_user),
    auth_service: AuthService = Injected(AuthService),
):
    """
    Custom authentication for conversation update endpoint.
    If agent.security_settings.token_based_auth is true, only accepts JWT tokens (rejects API keys).
    If agent.security_settings.token_based_auth is false, accepts both API keys and JWT tokens.

    Optimized to fetch conversation with agent in a single database query.
    """
    # Fetch conversation with operator and agent in a single query
    conversation, agent = await _get_conversation_with_agent(conversation_id)

    # If conversation or agent not found, fall back to standard auth
    if not conversation or not agent:
        await auth(request, api_key, user)
        return

    # Route to appropriate auth handler based on agent.security_settings.token_based_auth flag
    # Check if security_settings exists and token_based_auth is enabled
    token_based_auth = (
        agent.security_settings.token_based_auth 
        if agent.security_settings and agent.security_settings.token_based_auth 
        else False
    )
    if token_based_auth:
        await _handle_authenticated_agent(
            request, conversation_id, agent, api_key, user, auth_service
        )
    else:
        # Standard auth accepts both API key and JWT
        await auth(request, api_key, user)
