import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Request
from injector import inject
from sqlalchemy.exc import IntegrityError

from app.auth.utils import get_current_user_id, hash_api_key
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from app.db.mcp_auth_values import api_key_auth_values, merge_oauth2_auth_values, oauth2_auth_values
from app.repositories.mcp_server import MCPServerRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerUpdate,
    MCPServerWorkflowResponse,
)
from app.services.mcp_oauth_inbound import (
    extract_oauth_client_id_from_claims,
    looks_like_jwt,
    resolve_oauth2_issuer_url,
    unverified_jwt_claims,
    verify_oauth_access_token,
)

logger = logging.getLogger(__name__)


def _oauth2_issuer_url_for_create(oauth2_issuer_url: Optional[str]) -> str:
    """
    Canonical openid-configuration document URL to persist.
    """
    return (oauth2_issuer_url or "").strip()


def _coerce_auth_values_dict(raw: Any) -> Dict[str, Any]:
    """Normalize ORM JSONB / mapping types to a plain dict (isinstance(x, dict) can fail)."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if hasattr(raw, "items"):
        try:
            return dict(raw.items())
        except (TypeError, ValueError):
            pass
    return {}


def _public_auth_values_for_response(
    auth_t: str,
    av: Dict[str, Any],
    *,
    masked_api: Optional[str],
    include_admin_oauth_plaintext: bool,
) -> Dict[str, Any]:
    """
    Build auth_values for JSON responses.

    When include_admin_oauth_plaintext is True (management API), oauth2_client_id is decrypted
    for edit forms; client secret is never returned, only oauth2_client_secret_set.

    When False (in-memory use after MCP/JWT auth), omit sensitive fields.
    """
    if not include_admin_oauth_plaintext:
        return {}

    if auth_t == "oauth2":
        out: Dict[str, Any] = {}
        iss = av.get("oauth2_issuer_url")
        if iss is not None and str(iss).strip():
            out["oauth2_issuer_url"] = str(iss).strip()
        sc = av.get("oauth2_scope")
        if sc is not None and str(sc).strip():
            out["oauth2_scope"] = str(sc).strip()
        else:
            out["oauth2_scope"] = ""
        aud = av.get("oauth2_audience")
        if aud is not None and str(aud).strip():
            out["oauth2_audience"] = str(aud).strip()
        else:
            out["oauth2_audience"] = ""
        enc_cid = av.get("oauth2_client_id_encrypted")
        if enc_cid:
            out["oauth2_client_id"] = decrypt_key(str(enc_cid)) or None
        else:
            out["oauth2_client_id"] = None
        out["oauth2_client_secret_set"] = bool(av.get("oauth2_client_secret_encrypted"))
        return out

    out_api: Dict[str, Any] = {}
    if masked_api:
        out_api["api_key"] = masked_api
    return out_api


def _extract_input_schema_from_chat_input_node(workflow_model) -> Dict[str, Any]:
    """
    Extract input schema from the chatInputNode in a workflow.

    Args:
        workflow_model: WorkflowModel instance

    Returns:
        JSON Schema format input schema
    """
    # Default empty schema
    input_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    if not workflow_model or not workflow_model.nodes:
        return input_schema

    # Find the chatInputNode in the workflow's nodes
    chat_input_node = None
    for node in workflow_model.nodes:
        if isinstance(node, dict) and node.get("type") == "chatInputNode":
            chat_input_node = node
            break

    if not chat_input_node:
        logger.debug(f"No chatInputNode found in workflow {workflow_model.id}")
        return input_schema

    # Extract inputSchema from the chatInputNode's data
    node_data = chat_input_node.get("data", {})
    workflow_input_schema = node_data.get("inputSchema", {})

    if not workflow_input_schema:
        logger.debug(f"No inputSchema found in chatInputNode for workflow {workflow_model.id}")
        return input_schema

    # Convert workflow inputSchema format to JSON Schema format
    # Workflow format: { "field_name": { "type": "string", "required": false, "description": "..." } }
    # JSON Schema format: { "type": "object", "properties": { "field_name": { "type": "string", "description": "..." } }, "required": ["field_name"] }

    properties = {}
    required_fields = []

    for field_name, field_schema in workflow_input_schema.items():
        if isinstance(field_schema, dict):
            # Build property schema
            prop_schema = {
                "type": field_schema.get("type", "string"),
            }

            # Add description if present
            if "description" in field_schema:
                prop_schema["description"] = field_schema["description"]

            # Add default value if present
            if "defaultValue" in field_schema:
                prop_schema["default"] = field_schema["defaultValue"]
            elif "default" in field_schema:
                prop_schema["default"] = field_schema["default"]

            # Handle array items if type is array
            if prop_schema["type"] == "array" and "items" in field_schema:
                prop_schema["items"] = field_schema["items"]

            properties[field_name] = prop_schema

            # Check if field is required
            is_required = field_schema.get("required", False)
            if is_required:
                required_fields.append(field_name)

    input_schema["properties"] = properties
    if required_fields:
        input_schema["required"] = required_fields

    return input_schema


def _add_tenant_id_to_url(url: Optional[str], request: Optional[Request] = None) -> Optional[str]:
    if not request:
        return url
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return url
    return f"{url}?x-tenant-id={tenant_id}" if url else None

@inject
class MCPServerService:
    """Service for managing MCP servers."""

    def __init__(
        self,
        repo: MCPServerRepository,
        workflow_repo: WorkflowRepository,
    ):
        self.repo = repo
        self.workflow_repo = workflow_repo

    async def create(
        self, data: MCPServerCreate, request: Optional[Request] = None
    ) -> MCPServerResponse:
        """Create a new MCP server."""
        user_id = get_current_user_id()
        if not user_id:
            raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)

        # Check name uniqueness
        existing = await self.repo.get_by_name(data.name, user_id)
        if existing:
            raise AppException(
                status_code=400,
                error_key=ErrorKey.API_KEY_NAME_EXISTS,  # Reuse this error key
                error_detail=f"MCP server with name '{data.name}' already exists",
            )

        # Validate workflows exist and user has access
        workflow_ids = [wf.workflow_id for wf in data.workflows]
        workflows = await self.workflow_repo.get_by_ids(workflow_ids)

        if len(workflows) != len(workflow_ids):
            raise AppException(
                status_code=404,
                error_key=ErrorKey.WORKFLOW_NOT_FOUND,
                error_detail="One or more workflows not found",
            )

        # Check user has access to workflows (workflow.user_id matches or is None for shared)
        for workflow in workflows:
            if workflow.user_id and workflow.user_id != user_id:
                raise AppException(
                    status_code=403,
                    error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                    error_detail=f"User does not have access to workflow {workflow.id}",
                )

        # Prepare workflows data
        workflows_data = [
            {
                "workflow_id": wf.workflow_id,
                "tool_name": wf.tool_name,
                "tool_description": wf.tool_description,
            }
            for wf in data.workflows
        ]

        try:
            if data.auth_type == "api_key":
                assert data.api_key is not None
                auth_values = api_key_auth_values(
                    api_key_encrypted=encrypt_key(data.api_key),
                    api_key_hash=hash_api_key(data.api_key),
                )
                mcp_server = await self.repo.create(
                    name=data.name,
                    auth_type="api_key",
                    auth_values=auth_values,
                    user_id=user_id,
                    description=data.description,
                    is_active=data.is_active,
                    workflows=workflows_data,
                )
            else:
                assert data.oauth2_client_id and data.oauth2_client_secret
                iss = _oauth2_issuer_url_for_create(data.oauth2_issuer_url)
                aud = (data.oauth2_audience or "").strip() or None
                scope = (data.oauth2_scope or "").strip() or None
                cid = data.oauth2_client_id.strip()
                auth_values = oauth2_auth_values(
                    oauth2_client_id_encrypted=encrypt_key(cid),
                    oauth2_client_secret_encrypted=encrypt_key(data.oauth2_client_secret.strip()),
                    oauth2_issuer_url=iss,
                    oauth2_client_id_hash=hash_api_key(cid.lower()),
                    oauth2_audience=aud,
                    oauth2_scope=scope,
                )
                mcp_server = await self.repo.create(
                    name=data.name,
                    auth_type="oauth2",
                    auth_values=auth_values,
                    user_id=user_id,
                    description=data.description,
                    is_active=data.is_active,
                    workflows=workflows_data,
                )
        except IntegrityError as e:
            err = str(e.orig) if getattr(e, "orig", None) else str(e)
            if "uq_mcp_oauth_discovery_client" not in err and "uq_mcp_oauth_issuer_client" not in err:
                raise
            raise AppException(
                status_code=400,
                error_key=ErrorKey.API_KEY_NAME_EXISTS,
                error_detail="An MCP server already uses this OAuth2 issuer URL and client id combination",
            ) from None

        base_url = str(request.base_url).rstrip("/") if request else None
        return await self._to_response(mcp_server, base_url=base_url)

    async def get_by_id(
        self, mcp_server_id: UUID, request: Optional[Request] = None
    ) -> MCPServerResponse:
        """Get MCP server by ID."""
        user_id = get_current_user_id()
        if not user_id:
            raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)

        mcp_server = await self.repo.get_by_id(mcp_server_id, user_id)
        if not mcp_server:
            raise AppException(
                status_code=404,
                error_key=ErrorKey.WEBHOOK_NOT_FOUND,  # Reuse webhook error for now
                error_detail="MCP server not found",
            )

        base_url = str(request.base_url).rstrip("/") if request else None
        response = await self._to_response(mcp_server, base_url=base_url)
        response.url = _add_tenant_id_to_url(response.url, request)
        return response

    async def get_all(
        self, request: Optional[Request] = None
    ) -> List[MCPServerResponse]:
        """Get all MCP servers for the current user."""
        user_id = get_current_user_id()
        if not user_id:
            raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)

        mcp_servers = await self.repo.get_all(user_id)
        base_url = str(request.base_url).rstrip("/") if request else None
        # Build responses list by awaiting each coroutine
        responses = []
        for server in mcp_servers:
            response = await self._to_response(server, base_url=base_url)

            # when logged user context is a tenant we need to add tenant id on the url as query param
            response.url = _add_tenant_id_to_url(response.url, request)
            responses.append(response)
        return responses

    async def update(
        self,
        mcp_server_id: UUID,
        data: MCPServerUpdate,
        request: Optional[Request] = None,
    ) -> MCPServerResponse:
        """Update an MCP server."""
        user_id = get_current_user_id()
        if not user_id:
            raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)

        # Check server exists and user has access
        existing = await self.repo.get_by_id(mcp_server_id, user_id)
        if not existing:
            raise AppException(
                status_code=404,
                error_key=ErrorKey.WEBHOOK_NOT_FOUND,
                error_detail="MCP server not found",
            )

        # Check name uniqueness if name is being updated
        if data.name and data.name != existing.name:
            name_exists = await self.repo.get_by_name(data.name, user_id)
            if name_exists and name_exists.id != mcp_server_id:
                raise AppException(
                    status_code=400,
                    error_key=ErrorKey.API_KEY_NAME_EXISTS,
                    error_detail=f"MCP server with name '{data.name}' already exists",
                )

        # Validate workflows if provided
        workflows_data = None
        if data.workflows is not None:
            workflow_ids = [wf.workflow_id for wf in data.workflows]
            workflows = await self.workflow_repo.get_by_ids(workflow_ids)

            if len(workflows) != len(workflow_ids):
                raise AppException(
                    status_code=404,
                    error_key=ErrorKey.WORKFLOW_NOT_FOUND,
                    error_detail="One or more workflows not found",
                )

            # Check user has access to workflows
            for workflow in workflows:
                if workflow.user_id and workflow.user_id != user_id:
                    raise AppException(
                        status_code=403,
                        error_key=ErrorKey.NOT_AUTHORIZED_ACCESS_RESOURCE,
                        error_detail=f"User does not have access to workflow {workflow.id}",
                    )

            workflows_data = [
                {
                    "workflow_id": wf.workflow_id,
                    "tool_name": wf.tool_name,
                    "tool_description": wf.tool_description,
                }
                for wf in data.workflows
            ]

        existing_auth = existing.auth_type or "api_key"
        target_auth = data.auth_type if data.auth_type is not None else existing_auth

        new_auth_values: Optional[Dict[str, Any]] = None
        auth_type_for_repo: Optional[str] = target_auth if target_auth != existing_auth else None

        if target_auth == "oauth2":
            if existing_auth != "oauth2":
                if not data.oauth2_client_id or not data.oauth2_client_secret:
                    raise AppException(
                        status_code=400,
                        error_key=ErrorKey.API_KEY_NAME_EXISTS,
                        error_detail="Switching to OAuth2 requires oauth2_client_id and oauth2_client_secret",
                    )
                iss = _oauth2_issuer_url_for_create(data.oauth2_issuer_url)
                if not iss:
                    raise AppException(
                        status_code=400,
                        error_key=ErrorKey.API_KEY_NAME_EXISTS,
                        error_detail="Switching to OAuth2 requires oauth2_issuer_url",
                    )
                aud = (data.oauth2_audience or "").strip() or None
                scope = (data.oauth2_scope or "").strip() or None
                cid = data.oauth2_client_id.strip()
                new_auth_values = oauth2_auth_values(
                    oauth2_client_id_encrypted=encrypt_key(cid),
                    oauth2_client_secret_encrypted=encrypt_key(data.oauth2_client_secret.strip()),
                    oauth2_issuer_url=iss,
                    oauth2_client_id_hash=hash_api_key(cid.lower()),
                    oauth2_audience=aud,
                    oauth2_scope=scope,
                )
            else:
                prev = _coerce_auth_values_dict(existing.auth_values)
                updates: Dict[str, Any] = {}
                if data.oauth2_issuer_url is not None:
                    stripped_iss = data.oauth2_issuer_url.strip()
                    if not stripped_iss:
                        raise AppException(
                            status_code=400,
                            error_key=ErrorKey.API_KEY_NAME_EXISTS,
                            error_detail="oauth2_issuer_url cannot be empty",
                        )
                    else:
                        updates["oauth2_issuer_url"] = stripped_iss
                if data.oauth2_scope is not None:
                    updates["oauth2_scope"] = data.oauth2_scope.strip() or ""
                if data.oauth2_client_id is not None:
                    cid_stripped = data.oauth2_client_id.strip()
                    if not cid_stripped:
                        raise AppException(
                            status_code=400,
                            error_key=ErrorKey.API_KEY_NAME_EXISTS,
                            error_detail="oauth2_client_id cannot be empty",
                        )
                    updates["oauth2_client_id_encrypted"] = encrypt_key(cid_stripped)
                    updates["oauth2_client_id_hash"] = hash_api_key(cid_stripped.lower())
                if data.oauth2_client_secret is not None:
                    sec_stripped = data.oauth2_client_secret.strip()
                    if not sec_stripped:
                        raise AppException(
                            status_code=400,
                            error_key=ErrorKey.API_KEY_NAME_EXISTS,
                            error_detail="oauth2_client_secret cannot be empty",
                        )
                    updates["oauth2_client_secret_encrypted"] = encrypt_key(sec_stripped)
                if data.oauth2_audience is not None:
                    updates["oauth2_audience"] = data.oauth2_audience.strip() or ""
                if updates:
                    new_auth_values = merge_oauth2_auth_values(prev, updates)
        else:
            if existing_auth == "oauth2":
                if not data.api_key:
                    raise AppException(
                        status_code=400,
                        error_key=ErrorKey.API_KEY_NAME_EXISTS,
                        error_detail="Switching to API key auth requires a new api_key",
                    )
                new_auth_values = api_key_auth_values(
                    api_key_encrypted=encrypt_key(data.api_key),
                    api_key_hash=hash_api_key(data.api_key),
                )
            elif data.api_key:
                new_auth_values = api_key_auth_values(
                    api_key_encrypted=encrypt_key(data.api_key),
                    api_key_hash=hash_api_key(data.api_key),
                )

        try:
            updated = await self.repo.update(
                mcp_server_id=mcp_server_id,
                user_id=user_id,
                name=data.name,
                auth_type=auth_type_for_repo,
                auth_values=new_auth_values,
                description=data.description,
                is_active=data.is_active,
                workflows=workflows_data,
            )
        except IntegrityError as e:
            err = str(e.orig) if getattr(e, "orig", None) else str(e)
            if "uq_mcp_oauth_discovery_client" not in err and "uq_mcp_oauth_issuer_client" not in err:
                raise
            raise AppException(
                status_code=400,
                error_key=ErrorKey.API_KEY_NAME_EXISTS,
                error_detail="An MCP server already uses this OAuth2 issuer URL and client id combination",
            ) from None

        if not updated:
            raise AppException(
                status_code=404,
                error_key=ErrorKey.WEBHOOK_NOT_FOUND,
                error_detail="MCP server not found",
            )

        base_url = str(request.base_url).rstrip("/") if request else None
        return await self._to_response(updated, base_url=base_url)

    async def delete(self, mcp_server_id: UUID) -> bool:
        """Delete an MCP server (soft delete)."""
        user_id = get_current_user_id()
        if not user_id:
            raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)

        return await self.repo.delete(mcp_server_id, user_id)

    async def _authenticate_mcp_static_api_key(
        self, bearer_token: str
    ) -> Optional[MCPServerResponse]:
        """Resolve an MCP server by SHA-256 hash of the static key (``auth_type`` api_key only)."""
        mcp_server = await self.repo.get_by_api_key_hash(hash_api_key(bearer_token))
        if not mcp_server:
            return None
        auth_t = mcp_server.auth_type or "api_key"
        if auth_t != "api_key":
            return None
        if mcp_server.is_active != 1:
            return None
        return await self._to_response(mcp_server, base_url=None, redact_auth_for_protocol=True)

    async def _authenticate_mcp_oauth2_jwt(
        self, bearer_token: str
    ) -> Optional[MCPServerResponse]:
        """
        Resolve an OAuth2 MCP server by JWT client/application id (hashed), then verify the
        token with issuer and audience from that row via
        :func:`~app.services.mcp_oauth_inbound.verify_oauth_access_token`.
        """
        if not looks_like_jwt(bearer_token):
            return None

        claims = unverified_jwt_claims(bearer_token)
        if not claims:
            return None

        client_id = extract_oauth_client_id_from_claims(claims)
        if not client_id:
            return None

        client_id_hash = hash_api_key(client_id.strip().lower())
        mcp_server = await self.repo.get_by_oauth_client_id_hash(client_id_hash)
        if not mcp_server or (mcp_server.auth_type or "") != "oauth2":
            return None
        if mcp_server.is_active != 1:
            return None

        av = _coerce_auth_values_dict(getattr(mcp_server, "auth_values", None))
        iss = resolve_oauth2_issuer_url(av)
        if not iss:
            return None
        aud = av.get("oauth2_audience")
        if isinstance(aud, str) and not aud.strip():
            aud = None
        scope_raw = av.get("oauth2_scope")
        scope = str(scope_raw).strip() if scope_raw is not None else None

        if not await verify_oauth_access_token(bearer_token, iss, aud, scope):
            return None

        return await self._to_response(mcp_server, base_url=None, redact_auth_for_protocol=True)

    async def authenticate_mcp_bearer(self, bearer_token: str) -> Optional[MCPServerResponse]:
        """
        Authenticate hosted MCP traffic: try static API key first, then OAuth 2.0 JWT + JWKS verify.

        OAuth 2.0 servers are only accepted after :func:`~app.services.mcp_oauth_inbound.verify_oauth_access_token`
        succeeds (see :meth:`_authenticate_mcp_oauth2_jwt`).
        """
        bearer_token = (bearer_token or "").strip()
        if not bearer_token:
            return None

        by_key = await self._authenticate_mcp_static_api_key(bearer_token)
        if by_key:
            return by_key

        return await self._authenticate_mcp_oauth2_jwt(bearer_token)

    async def validate_api_key(self, bearer_token: str) -> Optional[MCPServerResponse]:
        """Alias for :meth:`authenticate_mcp_bearer` (same behavior)."""
        return await self.authenticate_mcp_bearer(bearer_token)

    async def _to_response(
        self,
        mcp_server,
        base_url: Optional[str] = None,
        *,
        redact_auth_for_protocol: bool = False,
    ) -> MCPServerResponse:
        """Convert MCP server model to response schema."""
        workflows = []
        for wf in mcp_server.workflows:
            # Extract input schema from workflow's chatInputNode
            workflow_model = None
            input_schema = None
            try:
                # Get workflow model to extract input schema
                # Note: workflow relationship might not be loaded, so we need to fetch it
                workflow_model = await self.workflow_repo.get_by_id(wf.workflow_id)
                if workflow_model:
                    input_schema = _extract_input_schema_from_chat_input_node(workflow_model)
            except Exception as e:
                logger.warning(f"Failed to extract input schema for workflow {wf.workflow_id}: {e}")

            workflows.append(
                MCPServerWorkflowResponse(
                    id=wf.id,
                    mcp_server_id=wf.mcp_server_id,
                    workflow_id=wf.workflow_id,
                    tool_name=wf.tool_name,
                    tool_description=wf.tool_description,
                    input_schema=input_schema,
                    created_at=wf.created_at,
                    updated_at=wf.updated_at,
                )
            )

        # Generate URL if base_url is provided
        url = None
        if base_url:
            # Format: {base_url}/api/mcp
            # The server_id is not part of the URL path — auth disambiguates (API key hash or JWT iss+client)
            url = f"{base_url.rstrip('/')}/api/mcp"

        auth_t = getattr(mcp_server, "auth_type", None) or "api_key"
        av = _coerce_auth_values_dict(getattr(mcp_server, "auth_values", None))
        masked_api = "***" if auth_t == "api_key" and av.get("api_key_hash") else None
        public_av = _public_auth_values_for_response(
            auth_t,
            av,
            masked_api=masked_api,
            include_admin_oauth_plaintext=not redact_auth_for_protocol,
        )

        return MCPServerResponse(
            id=mcp_server.id,
            name=mcp_server.name,
            url=url,
            auth_type=auth_t,
            auth_values=public_av,
            workflows=workflows,
            description=mcp_server.description,
            is_active=mcp_server.is_active,
            is_deleted=mcp_server.is_deleted,
            user_id=mcp_server.user_id,
            created_at=mcp_server.created_at,
            updated_at=mcp_server.updated_at,
        )
