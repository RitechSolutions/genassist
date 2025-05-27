from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, Optional

class DataSourceBase(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    source_type: Optional[str] = Field(None, max_length=255)
    connection_data: Optional[Dict[str, Any]] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)

class DataSourceCreate(DataSourceBase):
    name: str = Field(..., max_length=255)
    source_type: str = Field(..., max_length=255)
    connection_data: Dict[str, Any] = Field(...)
    is_active: int = Field(1, ge=0, le=1)

class DataSourceUpdate(DataSourceBase):
    pass

class DataSourceRead(DataSourceBase):
    id: UUID

    model_config = ConfigDict(
            from_attributes = True,
            )