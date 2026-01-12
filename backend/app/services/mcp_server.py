import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from injector import inject
from fastapi import Request

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.encryption_utils import encrypt_key
from app.auth.utils import get_current_user_id, hash_api_key
from app.repositories.mcp_server import MCPServerRepository
from app.repositories.workflow import WorkflowRepository
from app.schemas.mcp_server import (
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerResponse,
    MCPServerWorkflowResponse,
)

logger = logging.getLogger(__name__)


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

        # Encrypt API key
        encrypted_api_key = encrypt_key(data.api_key)
        api_key_hash = hash_api_key(data.api_key)

        # Prepare workflows data
        workflows_data = [
            {
                "workflow_id": wf.workflow_id,
                "tool_name": wf.tool_name,
                "tool_description": wf.tool_description,
            }
            for wf in data.workflows
        ]

        # Create MCP server
        mcp_server = await self.repo.create(
            name=data.name,
            api_key_encrypted=encrypted_api_key,
            api_key_hash=api_key_hash,
            user_id=user_id,
            description=data.description,
            is_active=data.is_active,
            workflows=workflows_data,
        )

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
        return await self._to_response(mcp_server, base_url=base_url)

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

        # Encrypt API key if provided
        api_key_encrypted = None
        api_key_hash = None
        if data.api_key:
            api_key_encrypted = encrypt_key(data.api_key)
            api_key_hash = hash_api_key(data.api_key)

        # Update MCP server
        updated = await self.repo.update(
            mcp_server_id=mcp_server_id,
            user_id=user_id,
            name=data.name,
            api_key_encrypted=api_key_encrypted,
            api_key_hash=api_key_hash,
            description=data.description,
            is_active=data.is_active,
            workflows=workflows_data,
        )

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

    async def validate_api_key(self, api_key: str) -> Optional[MCPServerResponse]:
        """Validate API key and return MCP server if valid."""
        api_key_hash = hash_api_key(api_key)
        mcp_server = await self.repo.get_by_api_key_hash(api_key_hash)

        if not mcp_server:
            return None

        # Check if server is active
        if mcp_server.is_active != 1:
            return None

        # No base_url for MCP protocol endpoints (not needed for tool listing/execution)
        return await self._to_response(mcp_server, base_url=None)

    async def _to_response(
        self, mcp_server, base_url: Optional[str] = None
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
            # The server_id is not part of the URL path - authentication is via API key
            url = f"{base_url.rstrip('/')}/api/mcp"

        return MCPServerResponse(
            id=mcp_server.id,
            name=mcp_server.name,
            url=url,
            api_key="***",  # Masked API key
            workflows=workflows,
            description=mcp_server.description,
            is_active=mcp_server.is_active,
            is_deleted=mcp_server.is_deleted,
            user_id=mcp_server.user_id,
            created_at=mcp_server.created_at,
            updated_at=mcp_server.updated_at,
        )
