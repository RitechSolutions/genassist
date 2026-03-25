from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class LlmCostRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_key: str
    model_key: str
    input_per_1k: float
    output_per_1k: float
    updated_at: datetime

    @field_serializer("input_per_1k", "output_per_1k")
    def serialize_input_output_per_1k(self, value: float) -> str:
        return f"{value:.4f}"


class LlmCostRateImportResult(BaseModel):
    inserted: int = Field(ge=0)
    updated: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
