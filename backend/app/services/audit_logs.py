from injector import inject

from app.repositories.audit_logs import AuditLogRepository
from app.schemas.audit_log import AuditLogSearchParams

@inject
class AuditLogService:
    """
    Handles audit log-related business logic.
    """

    def __init__(self, audit_log_repo: AuditLogRepository):
        self.audit_log_repo = audit_log_repo

    async def search_audit_logs(self, search_params: AuditLogSearchParams) :
        """
        Search audit logs with filters.
        Returns a list of audit logs matching the search criteria.
        """
        logs = await self.audit_log_repo.search_logs(search_params)
        return logs
