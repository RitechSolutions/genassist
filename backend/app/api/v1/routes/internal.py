import logging
from typing import Optional
from uuid import UUID

import jwt
from fastapi import APIRouter, Header
from fastapi_injector import Injected

from app.core.tenant_scope import set_tenant_context
from app.services.auth import AuthService
from app.services.agent_config import AgentConfigService
from app.modules.workflow.registry import RegistryItem

# Dependencies
from app.auth.dependencies import verify_internal_secret

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

# Shared schemas
from app.schemas.internal import AgentExecuteRequest
from app.schemas.auth import VerifyTokenRequest, VerifyTokenResponse

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/ws/verify-token",
    response_model=VerifyTokenResponse,
    summary="Verify a WebSocket token (internal use only)",
)
async def verify_ws_token(
    body: VerifyTokenRequest,
    _secret: str = Header(..., alias="x-internal-secret", include_in_schema=False),
    auth_service: AuthService = Injected(AuthService),
):
    """
    Internal endpoint called by the websocket to verify a token once
    on initial WebSocket connection. Returns user info and permissions.
    """
    # Verify internal secret
    verify_internal_secret(_secret)

    # Set tenant context for the lookup
    set_tenant_context(body.tenant_id)

    user_id: UUID
    perms: list[str]
    token_exp: Optional[int] = None

    if body.access_token:
        # Decode JWT and extract expiry
        try:
            raw_payload = jwt.decode(
                body.access_token,
                auth_service.secret_key,
                algorithms=[auth_service.algorithm],
                options={"verify_exp": False},
            )
            token_exp = raw_payload.get("exp")
        except Exception:
            token_exp = None

        user = await auth_service.decode_jwt(body.access_token)
        user_id = user.id
        perms = user.permissions
    elif body.api_key:
        key_obj = await auth_service.authenticate_api_key(body.api_key)
        user_id = key_obj.user.id
        perms = key_obj.permissions
    else:
        raise AppException(status_code=400, error_key=ErrorKey.MISSING_PARAMETER, error_detail="Either access_token or api_key is required")

    # Check required permissions
    if body.required_permissions:
        # permissions without wildcard
        _perm_without_wildcard = [p for p in perms if p != "*"]

        # check if the required permissions are subset of the user permissions
        if not ("*" in perms) and not set(_perm_without_wildcard).issubset(set(perms)):
            raise AppException(status_code=403, error_key=ErrorKey.INSUFFICIENT_PERMISSIONS, error_detail="Insufficient permissions")

    return VerifyTokenResponse(
        user_id=str(user_id),
        permissions=perms,
        tenant_id=body.tenant_id,
        token_exp=token_exp,
    )


@router.get(
    "/agents/{agent_id}/config",
    summary="Get agent configuration (internal use only)",
)
async def get_agent_config(
    agent_id: str,
    _secret: str = Header(..., alias="x-internal-secret", include_in_schema=False),
    agent_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Internal endpoint called by the websocket to fetch agent configuration
    for media-stream/Twilio endpoints.
    """
    verify_internal_secret(_secret)

    agent = await agent_service.get_by_id(agent_id)
    if not agent:
        raise AppException(status_code=404, error_key=ErrorKey.AGENT_NOT_FOUND, error_detail="Agent not found")

    return {
        "id": str(agent.id),
        "name": agent.name,
        "config": agent.config if hasattr(agent, "config") else None,
    }


@router.post(
    "/agents/execute",
    summary="Execute agent with text input (internal use only)",
)
async def execute_agent(
    body: AgentExecuteRequest,
    _secret: str = Header(..., alias="x-internal-secret", include_in_schema=False),
    agent_service: AgentConfigService = Injected(AgentConfigService),
):
    """
    Internal endpoint called by the websocket for Twilio media-stream.
    Passes transcribed text to the agent and returns the response.
    """
    verify_internal_secret(_secret)

    try:
        agent = await agent_service.get_by_id_full(UUID(body.agent_id))
        agent_item = RegistryItem(agent)
        agent_response = await agent_item.execute(
            session_message=body.text,
            metadata={"thread_id": body.thread_id},
        )
        output = agent_response.get("output")
        if not output:
            return {"success": False, "message": "Agent returned empty response"}
        return {"success": True, "message": output}
    except Exception as exc:
        logger.error(f"Agent execution error: {exc}")
        return {"success": False, "message": str(exc)}
