from typing import Optional, Dict, Literal
from uuid import UUID
from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from datetime import datetime

WebhookType = Literal["slack", "whatsapp", "generic"]

class WebhookBase(BaseModel):
    name: str
    url: str
    method: Literal["GET", "POST"]
    headers: Dict[str, str] = Field(default_factory=dict)
    secret: Optional[str] = None
    description: Optional[str] = None
    is_active: int = 1
    webhook_type: WebhookType = "generic"
    agent_id: Optional[UUID] = None
    app_settings_id: Optional[UUID] = None


class WebhookCreate(BaseModel):
    """Schema for creating a webhook - URL is auto-generated, not provided by user."""
    name: str
    method: Optional[Literal["GET", "POST"]] = "POST"
    headers: Optional[Dict[str, str]] = {}
    secret: Optional[str] = None
    description: Optional[str] = None
    is_active: int = 1
    webhook_type: WebhookType = "generic"
    agent_id: Optional[UUID] = None
    app_settings_id: Optional[UUID] = None
    base_url: Optional[str] = None

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    method: Optional[Literal["GET", "POST"]] = None
    headers: Optional[Dict[str, str]] = None
    secret: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None
    webhook_type: Optional[WebhookType] = None
    agent_id: Optional[UUID] = None
    app_settings_id: Optional[UUID] = None


class WebhookResponse(WebhookBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: int
    webhook_type: WebhookType
    agent_id: Optional[UUID] = None
    app_settings_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)
