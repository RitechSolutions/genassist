from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class TenantCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    domain: Optional[str] = None
    subdomain: Optional[str] = None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    database_name: str
    is_active: bool
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    is_active: Optional[bool] = None
