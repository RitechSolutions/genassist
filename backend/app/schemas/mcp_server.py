import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MCPServerWorkflowBase(BaseModel):
    """Base schema for MCP Server Workflow"""
    workflow_id: UUID
    tool_name: str = Field(..., min_length=1, description="Name to expose as MCP tool (lowercase with underscores)")
    tool_description: str = Field(..., min_length=1, description="Description for the MCP tool")

    @field_validator('tool_name')
    @classmethod
    def validate_tool_name(cls, v: str) -> str:
        """Validate tool name format: lowercase, alphanumeric, underscores only"""
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError('Tool name must be lowercase with alphanumeric characters and underscores only')
        return v


class MCPServerWorkflowCreate(MCPServerWorkflowBase):
    """Schema for creating an MCP Server Workflow"""
    pass  # noqa: WPS420


class MCPServerWorkflowResponse(MCPServerWorkflowBase):
    """Schema for MCP Server Workflow response"""
    id: UUID
    mcp_server_id: UUID
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Input schema extracted from chatInputNode (JSON Schema format)")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MCPServerBase(BaseModel):
    """Base schema for MCP Server"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    is_active: int = Field(default=1, ge=0, le=1)


class MCPServerCreate(BaseModel):
    """Schema for creating an MCP Server"""
    name: str = Field(..., min_length=1, max_length=255)
    auth_type: Literal["api_key", "oauth2"] = "api_key"
    # Omit these when auth_type is api_key vs oauth2; constraints enforced in model_validator only
    # (Field(default=None, min_length=…) can still surface as "required" in some FastAPI/Pydantic paths.)
    api_key: Optional[str] = Field(
        default=None,
        description="Required when auth_type is api_key (minimum 32 characters)",
    )
    oauth2_client_id: Optional[str] = Field(
        default=None, description="Required when auth_type is oauth2 (M2M client id)"
    )
    oauth2_client_secret: Optional[str] = Field(
        default=None, description="Required when auth_type is oauth2"
    )
    oauth2_issuer_url: Optional[str] = Field(
        default=None,
        description=(
            "When auth_type is oauth2 — full URL to openid-configuration "
            "(token/JWKS endpoints discovered from this document)"
        ),
    )
    oauth2_scope: Optional[str] = Field(
        default=None,
        description="Space-separated scopes — token request (outbound) or optional JWT scope/scp check (inbound)",
    )
    oauth2_audience: Optional[str] = Field(
        None,
        description="Optional expected JWT audience (aud) — comma-separated allowlist; omit to skip aud check",
    )
    workflows: List[MCPServerWorkflowCreate] = Field(..., min_length=1, description="List of workflows to expose as tools")
    description: Optional[str] = None
    is_active: int = Field(default=1, ge=0, le=1)

    @field_validator('workflows')
    @classmethod
    def validate_unique_tool_names(cls, v: List[MCPServerWorkflowCreate]) -> List[MCPServerWorkflowCreate]:
        """Ensure tool names are unique within the workflows list"""
        tool_names = [wf.tool_name for wf in v]
        if len(tool_names) != len(set(tool_names)):
            raise ValueError('Tool names must be unique within the workflows list')
        return v

    @model_validator(mode='after')
    def validate_auth_fields(self) -> Self:
        if self.auth_type == "api_key":
            raw = (self.api_key or "").strip()
            if not raw:
                raise ValueError("api_key is required when auth_type is api_key")
            if len(raw) < 32:
                raise ValueError("api_key must be at least 32 characters when auth_type is api_key")
        else:
            if not self.oauth2_client_id or not self.oauth2_client_id.strip():
                raise ValueError("oauth2_client_id is required when auth_type is oauth2")
            if not self.oauth2_client_secret or not self.oauth2_client_secret.strip():
                raise ValueError("oauth2_client_secret is required when auth_type is oauth2")
            iss = (self.oauth2_issuer_url or "").strip()
            if not iss:
                raise ValueError("oauth2_issuer_url is required when auth_type is oauth2")
            if len(iss) < 12:
                raise ValueError("oauth2_issuer_url is too short or invalid")
        return self


class MCPServerUpdate(BaseModel):
    """Schema for updating an MCP Server"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    auth_type: Optional[Literal["api_key", "oauth2"]] = None
    api_key: Optional[str] = Field(
        default=None,
        description="If set, must be at least 32 characters (api_key auth)",
    )
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    oauth2_issuer_url: Optional[str] = None
    oauth2_scope: Optional[str] = None
    oauth2_audience: Optional[str] = None
    workflows: Optional[List[MCPServerWorkflowCreate]] = Field(None, min_length=1)
    description: Optional[str] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)

    @field_validator("api_key")
    @classmethod
    def validate_api_key_length_if_set(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) < 32:
            raise ValueError("api_key must be at least 32 characters")
        return v

    @field_validator('workflows')
    @classmethod
    def validate_unique_tool_names(cls, v: Optional[List[MCPServerWorkflowCreate]]) -> Optional[List[MCPServerWorkflowCreate]]:
        """Ensure tool names are unique within the workflows list"""
        if v is None:
            return v
        tool_names = [wf.tool_name for wf in v]
        if len(tool_names) != len(set(tool_names)):
            raise ValueError('Tool names must be unique within the workflows list')
        return v


class MCPServerResponse(MCPServerBase):
    """Schema for MCP Server response"""

    id: UUID
    url: Optional[str] = Field(None, description="MCP server URL (generated by backend)")
    auth_type: str = Field(default="api_key", description="api_key or oauth2")
    auth_values: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Stored auth for the UI (management API only): "
            "api_key → {api_key: '***'} when configured; "
            "oauth2 → issuer URL, optional scope, audience, decrypted oauth2_client_id, "
            "oauth2_client_secret_set (bool; secret is never returned)"
        ),
    )
    workflows: List[MCPServerWorkflowResponse]
    is_deleted: int
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
