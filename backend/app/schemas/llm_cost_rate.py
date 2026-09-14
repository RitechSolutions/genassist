from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_serializer, field_validator

RateDecimal = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=10)]


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


CacheRateDecimal = Annotated[RateDecimal | None, BeforeValidator(_blank_to_none)]


def format_rate(value: Decimal | float | str) -> str:
    return f"{Decimal(str(value)).normalize():f}"


def _normalized_key(value: str) -> str:
    key = value.strip().lower()
    if not key:
        raise ValueError("must not be blank")
    return key


class LlmCostRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_key: str
    model_key: str
    input_per_1k: Decimal
    output_per_1k: Decimal
    cache_read_per_1k: Decimal | None = None
    cache_creation_per_1k: Decimal | None = None
    updated_at: datetime

    @field_serializer("input_per_1k", "output_per_1k")
    def serialize_input_output_per_1k(self, value: Decimal) -> str:
        return format_rate(value)

    @field_serializer("cache_read_per_1k", "cache_creation_per_1k")
    def serialize_cache_per_1k(self, value: Decimal | None) -> str | None:
        return None if value is None else format_rate(value)


class LlmCostRateImportResult(BaseModel):
    inserted: int = Field(ge=0)
    updated: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)


class LlmCostRateCreate(BaseModel):
    """Payload for creating a rate. Provider and model are trimmed and lowercased
    so the “already exists” check and the DB unique index use the same key"""

    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=512)
    input_per_1k: RateDecimal
    output_per_1k: RateDecimal
    cache_read_per_1k: CacheRateDecimal = None
    cache_creation_per_1k: CacheRateDecimal = None

    @field_validator("provider", "model")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _normalized_key(value)


class LlmCostRateUpdate(BaseModel):
    """Rate edit. Identity (provider/model) is fixed, delete + recreate to move a rate.
    Base rates are full-replace; a cache rate is only touched when the payload carries
    its key. Sent blank it clears back to the provider default, omitted it is kept"""

    input_per_1k: RateDecimal
    output_per_1k: RateDecimal
    cache_read_per_1k: CacheRateDecimal = None
    cache_creation_per_1k: CacheRateDecimal = None
