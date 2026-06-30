from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetryPolicy(BaseModel):
    retry_count: int = Field(default=0, ge=0, le=10, description="Extra attempts per provider beyond the first.")
    backoff_seconds: float = Field(default=0.0, ge=0, le=30, description="Initial backoff seconds; doubles each retry.")

    model_config = ConfigDict(from_attributes=True)


class FallbackChainBase(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    provider_ids: Optional[List[str]] = Field(
        default=None, description="Ordered LLM provider ids; index 0 is highest priority."
    )
    retry_policy: Optional[RetryPolicy] = None
    is_active: Optional[int] = 1

    model_config = ConfigDict(from_attributes=True)


class FallbackChainMinimal(BaseModel):
    id: UUID
    name: Optional[str] = None
    is_active: Optional[int] = 1

    model_config = ConfigDict(from_attributes=True)


class FallbackChainCreate(FallbackChainBase):
    name: str
    provider_ids: List[str]


class FallbackChainRead(FallbackChainBase):
    id: UUID


class FallbackChainUpdate(FallbackChainBase):
    pass
