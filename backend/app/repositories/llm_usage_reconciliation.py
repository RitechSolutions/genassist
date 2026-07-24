from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.llm_usage import LlmUsageReconciliationReportModel
from app.repositories.db_repository import DbRepository


@inject
class LlmUsageReconciliationRepository(DbRepository[LlmUsageReconciliationReportModel]):
    """Per-day shadow reconciliation reports"""

    def __init__(self, db: AsyncSession):
        super().__init__(LlmUsageReconciliationReportModel, db)

    async def recent_reports(self, limit: int) -> list[LlmUsageReconciliationReportModel]:
        """Most recent reports, newest day first."""
        result = await self.db.execute(
            select(LlmUsageReconciliationReportModel)
            .where(LlmUsageReconciliationReportModel.is_deleted == 0)
            .order_by(LlmUsageReconciliationReportModel.report_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
