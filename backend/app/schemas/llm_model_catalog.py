from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalized_provider(value: str) -> str:
    """Provider keys are matched against LLM_FORM_SCHEMAS, which is lowercase."""
    key = (value or "").strip().lower()
    if not key:
        raise ValueError("must not be blank")
    return key


def _trimmed_model(value: str) -> str:
    """Model ids are case sensitive for some providers, so only whitespace is stripped."""
    key = (value or "").strip()
    if not key:
        raise ValueError("must not be blank")
    return key


class LlmModelCatalogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_key: str
    model_key: str
    label: str
    is_active: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # True when a built-in model already uses this key: the row is kept but the
    # shipped entry is what the provider form serves.
    is_shadowed_by_builtin: bool = False


class LlmModelCatalogCreate(BaseModel):
    provider_key: str = Field(min_length=1, max_length=64)
    model_key: str = Field(min_length=1, max_length=512)
    label: str = Field(min_length=1, max_length=255)
    is_active: int = Field(default=1, ge=0, le=1)

    @field_validator("provider_key")
    @classmethod
    def _normalize_provider(cls, value: str) -> str:
        return _normalized_provider(value)

    @field_validator("model_key")
    @classmethod
    def _normalize_model(cls, value: str) -> str:
        return _trimmed_model(value)

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str) -> str:
        label = (value or "").strip()
        if not label:
            raise ValueError("must not be blank")
        return label


class LlmModelCatalogUpdate(BaseModel):
    """Identity (provider + model key) is fixed. Delete and re-add to move an entry,
    which keeps the key stable for the matching llm_cost_rates row."""

    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_active: Optional[int] = Field(default=None, ge=0, le=1)


class LlmModelCatalogProvider(BaseModel):
    """One selectable provider type, for the "add a model" form."""

    provider_key: str
    name: str
    builtin_model_keys: list[str] = Field(default_factory=list)
