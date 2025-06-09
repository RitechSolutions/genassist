from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.auth.dependencies import auth, permissions
from app.schemas.audit_log import AuditLogRead, AuditLogSearchParams
from app.services.audit_logs import AuditLogService
from datetime import datetime

router = APIRouter()

@router.get("/search", response_model=List[AuditLogRead], dependencies=[
    Depends(auth),
    Depends(permissions("read:audit_log"))
])
async def search(
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    action: str = Query(None),
    table_name: str = Query(None),
    entity_id: UUID = Query(None),
    modified_by: UUID = Query(None),
    limit:  int | None = Query(None, ge=1, le=500),
    offset: int | None = Query(None, ge=0),
    service: AuditLogService = Depends()
):
    """
    Search audit logs with optional filters:
    - start_date: Filter logs from this date
    - end_date: Filter logs until this date
    - action: Filter by action type (Insert, Update, Delete)
    - table_name: Filter by table name
    - entity_id: Filter by record UUID
    - modified_by: Filter by user UUID who made the change
    """
    search_params = AuditLogSearchParams(
        start_date=start_date,
        end_date=end_date,
        action=action,
        table_name=table_name,
        entity_id=entity_id,
        modified_by=modified_by,
        limit  = limit,
        offset = offset,
    )
    return await service.search_audit_logs(search_params)