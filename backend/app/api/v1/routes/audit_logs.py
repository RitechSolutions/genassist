from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.schemas.audit_log import AuditLogRead, AuditLogSearchParams, AuditLogSearchResult
from app.services.audit_logs import AuditLogService
from datetime import datetime
from app.core.permissions.constants import Permissions as P

router = APIRouter()

@router.get("/search", response_model=List[AuditLogSearchResult], dependencies=[
    Depends(auth),
    Depends(permissions(P.AuditLog.READ))
])
async def search(
    date_from: datetime = Query(None),
    date_to: datetime = Query(None),
    action: str = Query(None),
    table_name: str = Query(None),
    entity_id: UUID = Query(None),
    user: UUID = Query(None),
    limit:  int | None = Query(None, ge=1, le=500),
    offset: int | None = Query(None, ge=0),
    service: AuditLogService = Injected(AuditLogService),
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
        start_date=date_from,
        end_date=date_to,
        action=action,
        table_name=table_name,
        entity_id=entity_id,
        modified_by=user,
        limit=limit,
        offset=offset,
    )
    return await service.search_audit_logs(search_params)

@router.get("/{log_id}", response_model=AuditLogRead, dependencies=[
    Depends(auth),
    Depends(permissions(P.AuditLog.READ))
])
async def get_by_id(
    log_id: int,
    service: AuditLogService = Injected(AuditLogService),
):
    """
    Get a specific audit log entry by ID.
    """
    log = await service.get_audit_log_by_id(log_id)
    if log is None:
        raise HTTPException(status_code=404, detail=f"Audit log with ID {log_id} not found")
    return log