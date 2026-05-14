from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationItem(BaseModel):
    id: str
    title: str
    description: str
    timestamp: datetime
    type: str
    action_url: str
    group_id: str | None = None


class NotificationFeedResponse(BaseModel):
    items: list[NotificationItem]
    has_more: bool = False


class NotificationUserSettingsRead(BaseModel):
    conversation_started: bool
    conversation_hostility: bool
    conversation_finalized_hostility: bool
    workflow_failed: bool
    can_manage_workflow_failed: bool


class NotificationUserSettingsUpdate(BaseModel):
    conversation_started: bool | None = None
    conversation_hostility: bool | None = None
    conversation_finalized_hostility: bool | None = None
    workflow_failed: bool | None = None


class NotificationTypeTargetingRead(BaseModel):
    """Admin view: who receives each notification type."""

    type_key: str
    allow_all_tenant_users: bool
    user_ids: list[UUID] = Field(default_factory=list)
    group_ids: list[UUID] = Field(default_factory=list)


class NotificationAdminTargetingRead(BaseModel):
    types: list[NotificationTypeTargetingRead]


class NotificationTypeTargetingUpdate(BaseModel):
    allow_all_tenant_users: bool
    user_ids: list[UUID] = Field(default_factory=list)
    group_ids: list[UUID] = Field(default_factory=list)
