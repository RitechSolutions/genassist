from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


SupportTicketTypeLiteral = Literal["bug", "feature", "question"]


class SupportTicketEnvironment(BaseModel):
    os: Optional[str] = None
    browser: Optional[str] = None
    app_version: Optional[str] = None
    environment_name: Optional[str] = None
    tenant: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None


class SupportTicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    description: str = Field(default="", max_length=50000)
    ticket_type: SupportTicketTypeLiteral = "bug"
    priority: Optional[int] = Field(default=None, ge=1, le=4)
    tags: list[str] = Field(default_factory=list)
    environment: Optional[dict[str, Any]] = None
    duplicate_of_id: Optional[UUID] = None
    force_create: bool = False


class SupportTicketDuplicateCandidate(BaseModel):
    id: UUID
    title: str
    status: str
    vote_count: int
    azure_work_item_id: Optional[int] = None
    azure_url: Optional[str] = None
    similarity: Optional[str] = None


class SupportTicketRead(BaseModel):
    id: UUID
    reporter_user_id: UUID
    title: str
    description: str
    ticket_type: str
    status: str
    priority: Optional[int] = None
    tags: Optional[list[str]] = None
    environment: Optional[dict[str, Any]] = None
    azure_work_item_id: Optional[int] = None
    azure_project: Optional[str] = None
    azure_url: Optional[str] = None
    app_settings_id: Optional[UUID] = None
    duplicate_of_id: Optional[UUID] = None
    fingerprint: Optional[str] = None
    vote_count: int
    sync_error: Optional[str] = None
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SupportTicketListResponse(BaseModel):
    items: list[SupportTicketRead]
    total: int


class SupportTicketCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)


class SupportTicketCommentRead(BaseModel):
    id: UUID
    ticket_id: UUID
    author_user_id: UUID
    body: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SupportTicketLinkDuplicate(BaseModel):
    duplicate_of_id: UUID


class SupportTicketSearchDuplicatesQuery(BaseModel):
    title: str = Field(..., min_length=3)
    ticket_type: SupportTicketTypeLiteral = "bug"
    tags: list[str] = Field(default_factory=list)
    limit: int = Field(default=5, ge=1, le=20)


class AdoWebhookPayload(BaseModel):
    """Subset of Azure DevOps Service Hook workitem.updated payload."""

    subscriptionId: Optional[str] = None
    eventType: Optional[str] = None
    resource: Optional[dict[str, Any]] = None
