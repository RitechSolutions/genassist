from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class CustomerBase(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255, description="Customer full name")
    phone: Optional[str] = Field(None, max_length=100, description="Customer phone number")
    external_id: Optional[str] = Field(None, max_length=255, description="External ID from source system")
    is_active: Optional[int] = Field(1, description="Is the customer active (0/1)")
    source_ref: Optional[str] = Field(None, max_length=255, description="Source reference")

    model_config = ConfigDict(
        from_attributes=True
    )


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=100)
    external_id: Optional[str] = Field(None, max_length=255)
    is_active: Optional[int] = None
    source_ref: Optional[str] = Field(None, max_length=255)


class CustomerRead(CustomerBase):
    id: UUID

    model_config = ConfigDict(
        from_attributes=True,
    )