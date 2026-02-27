import logging
from typing import Optional
from uuid import UUID

import jwt
from fastapi import APIRouter, Header, HTTPException
from fastapi_injector import Injected
from pydantic import BaseModel

from app.core.config.settings import settings
from app.core.tenant_scope import set_tenant_context
from app.services.auth import AuthService
from app.services.agent_config import AgentConfigService
from app.modules.workflow.registry import RegistryItem

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_internal_secret(x_internal_secret: str = Header(...)):
    """Validate the shared secret header for internal service-to-service calls."""
    if not settings.WS_INTERNAL_SECRET:
        raise HTTPException(status_code=503, detail="WS_INTERNAL_SECRET not configured")
    if x_internal_secret != settings.WS_INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Invalid internal secret")


class VerifyTokenRequest(BaseModel):
    access_token: Optional[str] = None
    api_key: Optional[str] = None
    required_permissions: list[str] = []
    tenant_id: str = "master"


class VerifyTokenResponse(BaseModel):
    user_id: str
    permissions: list[str]
    tenant_id: str
    token_exp: Optional[int] = None


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
    _verify_internal_secret(_secret)

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
        raise HTTPException(status_code=400, detail="Either access_token or api_key is required")

    # Check required permissions
    if body.required_permissions:
        if not set(body.required_permissions).issubset(set(perms)):
            raise HTTPException(status_code=403, detail="Insufficient permissions")

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
    _verify_internal_secret(_secret)

    agent = await agent_service.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "id": str(agent.id),
        "name": agent.name,
        "config": agent.config if hasattr(agent, "config") else None,
    }


class AgentExecuteRequest(BaseModel):
    agent_id: str
    thread_id: str
    text: str


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
    _verify_internal_secret(_secret)

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
