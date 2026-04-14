from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.role import RoleRead
from app.schemas.user_auth import UserAuth


class ApiKeyBase(BaseModel):
    name: str = Field(..., min_length=4, max_length=255, description="API key name")
    is_active: Optional[int] = Field(1, description="Is the key active (0/1)")
    assigned_user_id: Optional[UUID] = Field(None, description="User id to assign this api key to an AI agent.")
    model_config = ConfigDict(
        from_attributes = True
    )

class ApiKeyCreate(ApiKeyBase):
    role_ids: list[UUID] = Field(..., description="List of role IDs associated with the API key")
    agent_id: Optional[UUID] = Field(None,
                                     description="Filed used to determine if api key is being created for agent to"
                                                 " assign agent permission.")
    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=730,
        description="If set, the key stops authenticating after this many days from creation (UTC). Omit for no expiry.",
    )

class ApiKeyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=4, max_length=255)
    is_active: Optional[int] = None
    role_ids: Optional[list[UUID]] = None


class ApiKeyRotate(BaseModel):
    """
    Rotate the raw secret. The new value is returned once in `key_val` (same as create).

    If overlap_seconds > 0, the previous secret remains valid until that instant (UTC),
    so integrations can be updated without a hard cutover.
    """

    overlap_seconds: int = Field(
        0,
        ge=0,
        le=604800,
        description="How long the previous secret remains valid (max 7 days). 0 = immediate cutover.",
    )


class ApiKeyRead(ApiKeyBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    user_id: UUID
    roles: list[RoleRead] = []
    key_val: str
    previous_hashed_expires_at: Optional[datetime] = Field(
        None,
        description="When set, the prior secret is accepted for API auth until this time (UTC).",
    )
    credential_expires_at: Optional[datetime] = Field(
        None,
        description="When set, this key record (current secret) is not accepted for API auth at or after this instant (UTC).",
    )

    model_config = ConfigDict(
            from_attributes = True,
            )


class ApiKeyInternal(BaseModel):
    permissions: list[str] = []
    roles: list[RoleRead] = []
    user: UserAuth

    model_config = ConfigDict(from_attributes=True)
