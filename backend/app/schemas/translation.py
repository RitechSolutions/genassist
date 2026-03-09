from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# --- Language schemas ---


class LanguageCreate(BaseModel):
    code: str
    name: str


class LanguageRead(BaseModel):
    id: UUID
    code: str
    name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


# --- Translation schemas ---


class TranslationCreate(BaseModel):
    key: str
    default: Optional[str] = None
    translations: dict[str, str] = {}


class TranslationUpdate(BaseModel):
    default: Optional[str] = None
    translations: Optional[dict[str, str]] = None


class TranslationRead(BaseModel):
    id: UUID
    key: str
    default: Optional[str] = None
    translations: dict[str, str] = {}

    model_config = ConfigDict(from_attributes=True)
