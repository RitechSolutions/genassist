from typing import Annotated, List
from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.audit_log import AuditLogRead, AuditLogSearchResult
from app.schemas.filter import AuditLogFilter
from app.services.audit_logs import AuditLogService
from app.core.permissions.constants import Permissions as P

router = APIRouter()

@router.get("/search", response_model=List[AuditLogSearchResult], dependencies=[
    Depends(auth),
    Depends(permissions(P.AuditLog.READ))
])
async def search(
    audit_log_filter: Annotated[AuditLogFilter, Depends()],
    service: AuditLogService = Injected(AuditLogService),
):
    """
    Search audit logs with optional filters:
    - date_from: Filter logs from this date
    - date_to: Filter logs until this date
    - action: Filter by action type (Insert, Update, Delete)
    - table_name: Filter by table name
    - entity_id: Filter by record UUID
    - user: Filter by user UUID who made the change
    """
    return await service.search_audit_logs(audit_log_filter)

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
        raise AppException(
            error_key=ErrorKey.AUDIT_LOG_NOT_FOUND,
            status_code=404,
            error_detail=f"Audit log with ID {log_id} not found",
        )
    return log