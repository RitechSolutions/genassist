import logging
from datetime import datetime

from app.core.utils.date_time_utils import utc_now
from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.node_execution_daily_stats import NodeExecutionDailyStatsModel
from app.db.base import generate_sequential_uuid

logger = logging.getLogger(__name__)


class AnalyticsAggregationRepository:
    @inject
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_last_aggregation_timestamp(self) -> datetime | None:
        """Return the latest last_aggregated_at across all agent daily stats rows."""
        stmt = select(func.max(AgentExecutionDailyStatsModel.last_aggregated_at))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_earliest_log_timestamp(self) -> datetime | None:
        """Return the earliest logged_at across all agent response logs."""
        stmt = select(func.min(AgentResponseLogModel.logged_at))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_response_logs_since(
        self, since: datetime, until: datetime, *, limit: int = 1000, offset: int = 0
    ) -> list[AgentResponseLogModel]:
        """Fetch a batch of agent response logs within [since, until] that are not soft-deleted."""
        stmt = (
            select(AgentResponseLogModel)
            .where(
                AgentResponseLogModel.logged_at >= since,
                AgentResponseLogModel.logged_at <= until,
                AgentResponseLogModel.is_deleted == 0,
            )
            .order_by(AgentResponseLogModel.logged_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def upsert_agent_daily_stats(self, stats_list: list[dict]) -> None:
        """
        Upsert agent daily stats rows.

        On conflict (agent_id, stat_date) the row is updated with the latest computed values.
        """
        if not stats_list:
            return

        now = utc_now()
        rows = []
        for s in stats_list:
            rows.append(
                {
                    "id": generate_sequential_uuid(),
                    "agent_id": s["agent_id"],
                    "stat_date": s["stat_date"],
                    "execution_count": s["execution_count"],
                    "success_count": s["success_count"],
                    "error_count": s["error_count"],
                    "avg_response_ms": s.get("avg_response_ms"),
                    "min_response_ms": s.get("min_response_ms"),
                    "max_response_ms": s.get("max_response_ms"),
                    "total_response_ms": s.get("total_response_ms"),
                    "total_nodes_executed": s["total_nodes_executed"],
                    "avg_success_rate": s.get("avg_success_rate"),
                    "total_success_rate_sum": s.get("total_success_rate_sum"),
                    "rag_used_count": s["rag_used_count"],
                    "unique_conversations": s["unique_conversations"],
                    "finalized_conversations": s.get("finalized_conversations", 0),
                    "in_progress_conversations": s.get("in_progress_conversations", 0),
                    "thumbs_up_count": s.get("thumbs_up_count", 0),
                    "thumbs_down_count": s.get("thumbs_down_count", 0),
                    "last_aggregated_at": now,
                    "is_deleted": 0,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        stmt = insert(AgentExecutionDailyStatsModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_agent_execution_daily_stats_agent_date",
            set_={
                "execution_count": stmt.excluded.execution_count,
                "success_count": stmt.excluded.success_count,
                "error_count": stmt.excluded.error_count,
                "avg_response_ms": stmt.excluded.avg_response_ms,
                "min_response_ms": stmt.excluded.min_response_ms,
                "max_response_ms": stmt.excluded.max_response_ms,
                "total_response_ms": stmt.excluded.total_response_ms,
                "total_nodes_executed": stmt.excluded.total_nodes_executed,
                "avg_success_rate": stmt.excluded.avg_success_rate,
                "total_success_rate_sum": stmt.excluded.total_success_rate_sum,
                "rag_used_count": stmt.excluded.rag_used_count,
                "unique_conversations": stmt.excluded.unique_conversations,
                "finalized_conversations": stmt.excluded.finalized_conversations,
                "in_progress_conversations": stmt.excluded.in_progress_conversations,
                "thumbs_up_count": stmt.excluded.thumbs_up_count,
                "thumbs_down_count": stmt.excluded.thumbs_down_count,
                "last_aggregated_at": stmt.excluded.last_aggregated_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def upsert_node_daily_stats(self, stats_list: list[dict]) -> None:
        """
        Upsert node daily stats rows.

        On conflict (agent_id, node_type, stat_date) the row is updated.
        """
        if not stats_list:
            return

        now = utc_now()
        rows = []
        for s in stats_list:
            rows.append(
                {
                    "id": generate_sequential_uuid(),
                    "agent_id": s["agent_id"],
                    "node_type": s["node_type"],
                    "stat_date": s["stat_date"],
                    "execution_count": s["execution_count"],
                    "success_count": s["success_count"],
                    "failure_count": s["failure_count"],
                    "unique_conversations": s.get("unique_conversations", 0),
                    "thumbs_up_count": s.get("thumbs_up_count", 0),
                    "thumbs_down_count": s.get("thumbs_down_count", 0),
                    "avg_execution_ms": s.get("avg_execution_ms"),
                    "min_execution_ms": s.get("min_execution_ms"),
                    "max_execution_ms": s.get("max_execution_ms"),
                    "total_execution_ms": s.get("total_execution_ms"),
                    "is_deleted": 0,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        stmt = insert(NodeExecutionDailyStatsModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_node_execution_daily_stats_agent_node_date",
            set_={
                "execution_count": stmt.excluded.execution_count,
                "success_count": stmt.excluded.success_count,
                "failure_count": stmt.excluded.failure_count,
                "unique_conversations": stmt.excluded.unique_conversations,
                "thumbs_up_count": stmt.excluded.thumbs_up_count,
                "thumbs_down_count": stmt.excluded.thumbs_down_count,
                "avg_execution_ms": stmt.excluded.avg_execution_ms,
                "min_execution_ms": stmt.excluded.min_execution_ms,
                "max_execution_ms": stmt.excluded.max_execution_ms,
                "total_execution_ms": stmt.excluded.total_execution_ms,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()
