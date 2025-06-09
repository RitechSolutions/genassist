from uuid import UUID
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.audit_log import AuditLogModel
from app.db.session import get_db
from app.schemas.audit_log import AuditLogSearchParams

class AuditLogRepository:
    """Repository for audit log-related database operations."""

    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db

    async def search_logs(self, search_params: AuditLogSearchParams) -> list[AuditLogModel]:
        """
        Search audit logs with filters.
        """
        query = select(AuditLogModel)

        # Apply filters based on search parameters
        if search_params.start_date:
            query = query.where(AuditLogModel.modified_at >= search_params.start_date)
        
        if search_params.end_date:
            query = query.where(AuditLogModel.modified_at <= search_params.end_date)
        
        if search_params.action:
            query = query.where(AuditLogModel.action_name == search_params.action)
        
        if search_params.table_name:
            query = query.where(AuditLogModel.table_name == search_params.table_name)
        
        if search_params.entity_id:
            query = query.where(AuditLogModel.record_id == search_params.entity_id)
        
        if search_params.modified_by:
            query = query.where(AuditLogModel.modified_by == search_params.modified_by)

        # Order by modified_at descending to get most recent changes first
        query = query.order_by(AuditLogModel.modified_at.desc())

        if search_params.offset is not None:
            query = query.offset(search_params.offset)
        if search_params.limit is not None:
            query = query.limit(search_params.limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, log_id: int) -> AuditLogModel:
        """
        Get a specific audit log entry by ID.
        """
        query = select(AuditLogModel).where(AuditLogModel.id == log_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_table_and_record(self, table_name: str, record_id: UUID) -> list[AuditLogModel]:
        """
        Get all audit logs for a specific record in a table.
        """
        query = (
            select(AuditLogModel)
            .where(AuditLogModel.table_name == table_name)
            .where(AuditLogModel.record_id == record_id)
            .order_by(AuditLogModel.modified_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_recent_changes(self, limit: int = 100) -> list[AuditLogModel]:
        """
        Get the most recent audit log entries.
        """
        query = (
            select(AuditLogModel)
            .order_by(AuditLogModel.modified_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return result.scalars().all() 