from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TranslationBase(BaseModel):
    key: str
    default: Optional[str] = None
    en: Optional[str] = None
    es: Optional[str] = None
    fr: Optional[str] = None
    de: Optional[str] = None
    pt: Optional[str] = None
    zh: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TranslationCreate(TranslationBase):
    pass


class TranslationUpdate(BaseModel):
    default: Optional[str] = None
    en: Optional[str] = None
    es: Optional[str] = None
    fr: Optional[str] = None
    de: Optional[str] = None
    pt: Optional[str] = None
    zh: Optional[str] = None


class TranslationRead(TranslationBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
