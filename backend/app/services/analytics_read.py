import logging
from datetime import date
from uuid import UUID

from injector import inject

from app.repositories.analytics_read import AnalyticsReadRepository
from app.schemas.analytics import (
    AgentDailyStatsItem,
    AgentDailyStatsListResponse,
    AgentStatsSummaryResponse,
    NodeDailyStatsItem,
    NodeDailyStatsListResponse,
    NodeTypeBreakdownItem,
    NodeTypeBreakdownResponse,
)

logger = logging.getLogger(__name__)


class AnalyticsReadService:
    @inject
    def __init__(self, repo: AnalyticsReadRepository):
        self.repo = repo

    async def get_agent_daily_stats(
        self,
        agent_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> AgentDailyStatsListResponse:
        rows = await self.repo.get_agent_daily_stats(
            agent_id=agent_id, from_date=from_date, to_date=to_date
        )
        items = [AgentDailyStatsItem.model_validate(r) for r in rows]
        return AgentDailyStatsListResponse(items=items, total=len(items))

    async def get_agent_stats_summary(
        self,
        agent_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> AgentStatsSummaryResponse:
        summary = await self.repo.get_agent_stats_summary(
            agent_id=agent_id, from_date=from_date, to_date=to_date
        )
        return AgentStatsSummaryResponse(
            agent_id=agent_id,
            from_date=from_date,
            to_date=to_date,
            total_executions=summary["total_executions"],
            total_success=summary["total_success"],
            total_errors=summary["total_errors"],
            avg_response_ms=summary.get("avg_response_ms"),
            avg_success_rate=summary.get("avg_success_rate"),
            total_rag_used=summary["total_rag_used"],
            total_unique_conversations=summary["total_unique_conversations"],
            total_thumbs_up=summary.get("total_thumbs_up", 0),
            total_thumbs_down=summary.get("total_thumbs_down", 0),
        )

    async def get_node_daily_stats(
        self,
        agent_id: UUID | None = None,
        node_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> NodeDailyStatsListResponse:
        rows = await self.repo.get_node_daily_stats(
            agent_id=agent_id, node_type=node_type, from_date=from_date, to_date=to_date
        )
        items = [NodeDailyStatsItem.model_validate(r) for r in rows]
        return NodeDailyStatsListResponse(items=items, total=len(items))

    async def get_node_type_breakdown(
        self,
        agent_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> NodeTypeBreakdownResponse:
        rows = await self.repo.get_node_type_breakdown(
            agent_id=agent_id, from_date=from_date, to_date=to_date
        )
        items = []
        for r in rows:
            exec_count = r["execution_count"] or 0
            success_count = r["success_count"] or 0
            success_rate = (success_count / exec_count) if exec_count > 0 else None
            items.append(
                NodeTypeBreakdownItem(
                    node_type=r["node_type"],
                    execution_count=exec_count,
                    success_count=success_count,
                    failure_count=r["failure_count"] or 0,
                    success_rate=success_rate,
                    avg_execution_ms=r.get("avg_execution_ms"),
                    total_execution_ms=r.get("total_execution_ms"),
                )
            )
        return NodeTypeBreakdownResponse(
            agent_id=agent_id,
            from_date=from_date,
            to_date=to_date,
            items=items,
        )
