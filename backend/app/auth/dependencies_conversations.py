"""
Conversation-scoped authentication for HTTP and WebSocket endpoints.

Handles guest JWT tokens, token_based_auth agents, and session-only API key
restrictions for public embed integrations.
"""

import logging
from typing import Awaitable, Callable, Optional
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import Depends, Query, Request, WebSocket, WebSocketException, status
from fastapi_injector import Injected
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from starlette_context import context
from starlette_context.errors import ContextDoesNotExistError

from app.auth.dependencies import _set_user_context, auth, get_current_user
from app.auth.utils import api_key_header, has_permission, oauth2
from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import set_tenant_context
from app.schemas.socket_principal import SocketPrincipal
from app.schemas.user import UserReadAuth
from app.services.agent_config import AgentConfigService
from app.services.auth import AuthService
from app.services.conversations import ConversationService

logger = logging.getLogger(__name__)


def _auth_mode() -> str | None:
    try:
        return context.get("auth_mode")
    except ContextDoesNotExistError:
        return None


async def _soft_load_agent(
    request: Request,
    conversation_id: UUID,
    conversation_service: ConversationService,
    agent_config_service: AgentConfigService,
):
    """Load agent from conversation without raising 404 (for GET auth chain)."""
    if getattr(request.state, "agent", None):
        return request.state.agent

    conversation = await conversation_service.get_conversation_by_id_with_operator_agent(conversation_id)
    if conversation is None:
        return None

    operator = conversation.operator
    agent = operator.agent if operator else None
    if agent is None and operator:
        agent = await agent_config_service.get_by_operator_id(operator.id)

    if agent:
        request.state.agent = agent
    return agent


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
    except AppException:
        return False

    if guest_token_data["conversation_id"] != str(conversation_id):
        raise AppException(
            status_code=403,
            error_key=ErrorKey.NOT_AUTHORIZED,
            error_detail="Token is not valid for this conversation",
        )

    guest_user_id = guest_token_data.get("user_id")
    user_id_uuid = UUID(guest_user_id) if guest_user_id and isinstance(guest_user_id, str) else guest_user_id

    request.state.guest_token = guest_token_data
    request.state.user = None
    context["auth_mode"] = "guest_token"
    context["user_id"] = user_id_uuid
    context["user_roles"] = []
    context["operator_id"] = agent.operator.id if agent and agent.operator else None

    return True


async def _handle_authenticated_agent(
    request: Request,
    conversation_id: UUID,
    agent,
    api_key: Optional[str],
    user: Optional[UserReadAuth],
    auth_service: AuthService,
):
    """Handle authentication when agent.security_settings.token_based_auth is true (JWT only)."""
    if getattr(request.state, "api_key", None):
        raise AppException(
            status_code=403,
            error_key=ErrorKey.NOT_AUTHORIZED,
            error_detail="This agent requires JWT token authentication. API keys are not allowed.",
        )

    try:
        token_str = await oauth2(request)
        if token_str and await _handle_guest_token(request, token_str, conversation_id, auth_service, agent):
            return
    except (AppException, Exception):
        pass

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


def _agent_token_based_auth(agent) -> bool:
    return bool(
        agent
        and agent.security_settings
        and agent.security_settings.token_based_auth
    )


async def _conversation_token_based_auth(
    conversation_id: UUID,
    conversation_service: ConversationService,
    agent_config_service: AgentConfigService,
) -> bool:
    conversation = await conversation_service.get_conversation_by_id_with_operator_agent(conversation_id)
    if conversation is None:
        return False
    operator = conversation.operator
    agent = operator.agent if operator else None
    if agent is None and operator:
        agent = await agent_config_service.get_by_operator_id(operator.id)
    return _agent_token_based_auth(agent)


async def auth_for_conversation(
    request: Request,
    conversation_id: UUID,
    api_key: Optional[str] = Depends(api_key_header),
    user: Optional[UserReadAuth] = Depends(get_current_user),
    auth_service: AuthService = Injected(AuthService),
    conversation_service: ConversationService = Injected(ConversationService),
    agent_config_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Agent-aware authentication for conversation-scoped HTTP endpoints.

    If agent.security_settings.token_based_auth is true, only accepts JWT tokens (rejects API keys).
    If false (legacy mode), accepts ai-agent API keys without a guest JWT.
    """
    agent = getattr(request.state, "agent", None)
    if not agent:
        agent = await _soft_load_agent(request, conversation_id, conversation_service, agent_config_service)

    token_based_auth = _agent_token_based_auth(agent)

    if not agent:
        await auth(request, api_key, user)
        return

    try:
        token_str = await oauth2(request)
        if token_str and await _handle_guest_token(
            request, token_str, conversation_id, auth_service, agent
        ):
            return
    except AppException:
        raise
    except Exception:
        pass

    if token_based_auth:
        await _handle_authenticated_agent(request, conversation_id, agent, api_key, user, auth_service)
    else:
        await auth(request, api_key, user)


# Backward-compatible alias
auth_for_conversation_update = auth_for_conversation


def permissions_for_conversation(*required_permissions: str) -> Callable[[Request], Awaitable[None]]:
    """
    Permission gate for conversation endpoints.

    Skips RBAC for API keys when token_based_auth is disabled (auth layer already
    enforced guest/scoped access). Always checks guest tokens and JWT users.
    """

    async def wrapper(request: Request):
        # Only apply guest-scoped permissions when auth chose guest mode.
        # guest_token may remain on request.state while the caller authenticated
        # via JWT or API key (auth_mode token / api_key).
        if _auth_mode() == "guest_token":
            guest_token = getattr(request.state, "guest_token", None)
            if not guest_token:
                raise AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED)
            guest_permissions = guest_token.get("permissions", [])
            if not has_permission(guest_permissions, *required_permissions):
                raise AppException(ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)
            return

        agent = getattr(request.state, "agent", None)
        token_based_auth = _agent_token_based_auth(agent)

        if getattr(request.state, "api_key", None) and not token_based_auth:
            if not has_permission(request.state.api_key.permissions, *required_permissions):
                raise AppException(ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)
            return

        if getattr(request.state, "api_key", None):
            if not has_permission(request.state.api_key.permissions, *required_permissions):
                raise AppException(ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)
        elif getattr(request.state, "user", None):
            if not has_permission(request.state.user.permissions, *required_permissions):
                raise AppException(ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE, status_code=403)
        else:
            raise AppException(status_code=403, error_key=ErrorKey.NOT_AUTHORIZED)

    return wrapper


def socket_auth_conversation(required_permissions: list[str]):
    """
    WebSocket auth for conversation-scoped endpoints.

    Supports guest JWT (bound to conversation_id). Session-only API key rejection applies
    only when the agent has token_based_auth enabled; legacy agents accept ai-agent keys.
    """

    async def _auth_dependency(
        websocket: WebSocket,
        conversation_id: UUID,
        access_token: str | None = Query(default=None),
        api_key: str | None = Query(default=None),
        auth_service=Injected(AuthService),
    ) -> SocketPrincipal:
        try:
            resolved_tenant_id = None
            tenant_slug = None
            tenant_header_name = settings.TENANT_HEADER_NAME.lower()

            if settings.MULTI_TENANT_ENABLED:
                query_params = {}
                if websocket.url.query:
                    query_params = parse_qs(websocket.url.query)
                    tenant_query_param = (
                        query_params.get(tenant_header_name, [None])[0]
                        or query_params.get("tenant_id", [None])[0]
                        or query_params.get("tenant", [None])[0]
                    )
                    if tenant_query_param:
                        tenant_slug = tenant_query_param
                        resolved_tenant_id = tenant_slug
                        logger.debug(f"WebSocket tenant resolved from query parameter: {tenant_slug}")

                if not resolved_tenant_id and tenant_header_name in websocket.headers:
                    tenant_slug = websocket.headers[tenant_header_name]
                    resolved_tenant_id = tenant_slug
                    logger.debug(f"WebSocket tenant resolved from header: {tenant_slug}")

                if not resolved_tenant_id and settings.TENANT_SUBDOMAIN_ENABLED:
                    host = websocket.headers.get("host", "")
                    if "." in host:
                        subdomain = host.split(".")[0]
                        if subdomain and subdomain != "www":
                            tenant_slug = subdomain
                            resolved_tenant_id = tenant_slug
                            logger.debug(f"WebSocket tenant resolved from subdomain: {tenant_slug}")

            resolved_tenant_id = resolved_tenant_id or "master"
            set_tenant_context(resolved_tenant_id)
            logger.debug(f"WebSocket tenant context set: {resolved_tenant_id}")

            from app.dependencies.injector import injector
            conversation_service = injector.get(ConversationService)
            agent_config_service = injector.get(AgentConfigService)

            if access_token:
                guest_handled = False
                try:
                    guest_data = await auth_service.decode_guest_token(access_token)
                    if guest_data["conversation_id"] != str(conversation_id):
                        raise WebSocketException(
                            code=4403,
                            reason="Token is not valid for this conversation",
                        )
                    guest_user_id = guest_data.get("user_id")
                    if not guest_user_id:
                        raise WebSocketException(code=4401, reason="Invalid guest token")
                    from app.services.users import UserService

                    user_service = injector.get(UserService)
                    user = await user_service.get_by_id_for_auth(UUID(str(guest_user_id)))
                    if user is None or not user.is_active:
                        raise WebSocketException(code=4401, reason="Invalid guest token")
                    guest_perms = list(guest_data.get("permissions", []))
                    if P.Conversation.READ_IN_PROGRESS not in guest_perms:
                        guest_perms.append(P.Conversation.READ_IN_PROGRESS)
                    principal, user_id, perms = (
                        user,
                        user.id,
                        guest_perms,
                    )
                    _set_user_context(user, user.roles)
                    guest_handled = True
                except AppException:
                    guest_handled = False

                if not guest_handled:
                    user = await auth_service.decode_jwt(access_token)
                    principal, user_id, perms = user, user.id, user.permissions
                    _set_user_context(user, user.roles)
            elif api_key:
                key_obj = await auth_service.authenticate_api_key(api_key)
                principal, user_id, perms = (
                    key_obj,
                    key_obj.user.id,
                    key_obj.permissions,
                )
                _set_user_context(key_obj.user, key_obj.roles)
                token_based_auth = await _conversation_token_based_auth(
                    conversation_id, conversation_service, agent_config_service
                )
                if token_based_auth and not has_permission(perms, P.Conversation.READ):
                    raise WebSocketException(
                        code=4403,
                        reason="Guest token required for in-progress conversation access",
                    )
            else:
                raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing credentials")

            if "*" not in perms and not set(required_permissions).issubset(set(perms)):
                raise WebSocketException(code=4403, reason="Invalid permissions")

            return SocketPrincipal(principal, user_id, perms, resolved_tenant_id)

        except ExpiredSignatureError:
            raise WebSocketException(code=4401, reason="Token expired")
        except InvalidTokenError:
            raise WebSocketException(code=4401, reason="Invalid token")

    return Depends(_auth_dependency)
