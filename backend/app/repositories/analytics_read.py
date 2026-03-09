import logging
from datetime import date
from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.node_execution_daily_stats import NodeExecutionDailyStatsModel

logger = logging.getLogger(__name__)


class AnalyticsReadRepository:
    @inject
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_agent_daily_stats(
        self,
        agent_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[AgentExecutionDailyStatsModel]:
        stmt = select(AgentExecutionDailyStatsModel).where(
            AgentExecutionDailyStatsModel.is_deleted == 0
        )
        if agent_id is not None:
            stmt = stmt.where(AgentExecutionDailyStatsModel.agent_id == agent_id)
        if from_date is not None:
            stmt = stmt.where(AgentExecutionDailyStatsModel.stat_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(AgentExecutionDailyStatsModel.stat_date <= to_date)
        stmt = stmt.order_by(AgentExecutionDailyStatsModel.stat_date)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_node_daily_stats(
        self,
        agent_id: UUID | None = None,
        node_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[NodeExecutionDailyStatsModel]:
        stmt = select(NodeExecutionDailyStatsModel).where(
            NodeExecutionDailyStatsModel.is_deleted == 0
        )
        if agent_id is not None:
            stmt = stmt.where(NodeExecutionDailyStatsModel.agent_id == agent_id)
        if node_type is not None:
            stmt = stmt.where(NodeExecutionDailyStatsModel.node_type == node_type)
        if from_date is not None:
            stmt = stmt.where(NodeExecutionDailyStatsModel.stat_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(NodeExecutionDailyStatsModel.stat_date <= to_date)
        stmt = stmt.order_by(NodeExecutionDailyStatsModel.stat_date, NodeExecutionDailyStatsModel.node_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_agent_stats_summary(
        self,
        agent_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        stmt = select(
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.execution_count), 0).label("total_executions"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.success_count), 0).label("total_success"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.error_count), 0).label("total_errors"),
            # Weighted average: avoids averaging daily averages when execution counts differ
            (
                func.sum(AgentExecutionDailyStatsModel.avg_response_ms * AgentExecutionDailyStatsModel.execution_count)
                / func.nullif(func.sum(AgentExecutionDailyStatsModel.execution_count), 0)
            ).label("avg_response_ms"),
            func.avg(AgentExecutionDailyStatsModel.avg_success_rate).label("avg_success_rate"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.rag_used_count), 0).label("total_rag_used"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.unique_conversations), 0).label("total_unique_conversations"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.finalized_conversations), 0).label("total_finalized_conversations"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.in_progress_conversations), 0).label("total_in_progress_conversations"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.thumbs_up_count), 0).label("total_thumbs_up"),
            func.coalesce(func.sum(AgentExecutionDailyStatsModel.thumbs_down_count), 0).label("total_thumbs_down"),
        ).where(AgentExecutionDailyStatsModel.is_deleted == 0)

        if agent_id is not None:
            stmt = stmt.where(AgentExecutionDailyStatsModel.agent_id == agent_id)
        if from_date is not None:
            stmt = stmt.where(AgentExecutionDailyStatsModel.stat_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(AgentExecutionDailyStatsModel.stat_date <= to_date)

        result = await self.db.execute(stmt)
        row = result.mappings().one()
        return dict(row)

    async def get_node_type_breakdown(
        self,
        agent_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        stmt = select(
            NodeExecutionDailyStatsModel.node_type,
            func.sum(NodeExecutionDailyStatsModel.execution_count).label("execution_count"),
            func.sum(NodeExecutionDailyStatsModel.success_count).label("success_count"),
            func.sum(NodeExecutionDailyStatsModel.failure_count).label("failure_count"),
            # Weighted average via pre-stored total_execution_ms sum
            (
                func.sum(NodeExecutionDailyStatsModel.total_execution_ms)
                / func.nullif(func.sum(NodeExecutionDailyStatsModel.execution_count), 0)
            ).label("avg_execution_ms"),
            func.sum(NodeExecutionDailyStatsModel.total_execution_ms).label("total_execution_ms"),
        ).where(
            NodeExecutionDailyStatsModel.agent_id == agent_id,
            NodeExecutionDailyStatsModel.is_deleted == 0,
        )

        if from_date is not None:
            stmt = stmt.where(NodeExecutionDailyStatsModel.stat_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(NodeExecutionDailyStatsModel.stat_date <= to_date)

        stmt = stmt.group_by(NodeExecutionDailyStatsModel.node_type).order_by(
            func.sum(NodeExecutionDailyStatsModel.execution_count).desc()
        )

        result = await self.db.execute(stmt)
        rows = result.mappings().all()
        return [dict(r) for r in rows]
