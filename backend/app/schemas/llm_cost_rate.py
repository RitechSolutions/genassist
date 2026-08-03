from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

RateDecimal = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=10)]


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
    updated_at: datetime

    @field_serializer("input_per_1k", "output_per_1k")
    def serialize_input_output_per_1k(self, value: Decimal) -> str:
        return format_rate(value)


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

    @field_validator("provider", "model")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return _normalized_key(value)


class LlmCostRateUpdate(BaseModel):
    """Rate edit. Identity (provider/model) is fixed, delete + recreate to move a rate"""

    input_per_1k: RateDecimal
    output_per_1k: RateDecimal
