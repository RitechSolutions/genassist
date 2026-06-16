from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class AuditLogBase(BaseModel):
    """Base schema for audit log with common fields."""
    id: int
    table_name: str
    record_id: UUID
    action_name: str
    modified_at: datetime
    modified_by: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogSearchResult(AuditLogBase):
    """Schema for audit log search results - excludes json_changes."""
    pass


class AuditLogRead(AuditLogBase):
    """Schema for individual audit log detail - includes json_changes."""
    json_changes: Optional[str] = None