from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class AuditLogSearchParams(BaseModel):
    start_date: Optional[datetime] | None = None
    end_date: Optional[datetime] | None = None
    action: Optional[str] | None = None
    table_name: Optional[str] | None = None
    entity_id: Optional[UUID] | None = None
    modified_by: Optional[UUID] | None = None
    limit:  Optional[int] = None
    offset: Optional[int] = None

class AuditLogRead(BaseModel):
    id: int
    table_name: str
    record_id: UUID
    action_name: str
    json_changes: Optional[str] = None
    modified_at: datetime
    modified_by: Optional[UUID] = None

    model_config = ConfigDict(
            from_attributes = True,
            )