from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateListItem(BaseModel):
    """Minimal template data for the gallery grid."""

    id: UUID
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    node_types: List[str] = Field(default_factory=list)
    node_count: int = 0
    install_count: int = 0
    is_official: bool = False
    # True for approved, cross-tenant (community) templates served from the master DB.
    is_global: bool = False
    # For the owner's own templates that have been published: pending/approved/rejected.
    publish_status: Optional[str] = None
    # Slug of the tenant a published/community template came from.
    source_tenant: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TemplateRead(TemplateListItem):
    """Full template incl. the sanitized graph and default agent config."""

    graph: Dict[str, Any]
    agent_config: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TemplateCreateFromAgent(BaseModel):
    """Save one of the user's own agents as a private template."""

    agent_id: UUID
    title: str = Field(..., max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=60)
    icon: Optional[str] = Field(None, max_length=60)
    tags: List[str] = Field(default_factory=list)


class TemplateInstallRequest(BaseModel):
    """Optional overrides when installing a template into the tenant."""

    name: Optional[str] = Field(None, max_length=100)


class TemplateInstallResponse(BaseModel):
    agent_id: UUID
    workflow_id: UUID


class TemplateRejectRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)
