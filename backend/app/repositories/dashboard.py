from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from injector import inject
from sqlalchemy import and_, case, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.utils.date_time_utils import utc_day_start
from app.db.events.group_scope import get_group_scope_clause
from app.db.models.agent import AgentModel
from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.app_settings import AppSettingsModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm_usage import LlmUsageEventModel
from app.db.models.operator import OperatorModel


def _ledger_window(from_date: datetime, to_date: datetime) -> tuple[datetime, datetime]:
    start = utc_day_start(from_date)
    if from_date > start:
        start += timedelta(days=1)
    return start, utc_day_start(to_date) + timedelta(days=1)


@inject
class DashboardRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_agents_count(self) -> int:
        """Get count of active agents."""
        query = select(func.count(AgentModel.id)).where(
            AgentModel.is_active == 1,
            AgentModel.is_deleted == 0
        )
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_workflow_runs_count(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> int:
        """
        Get count of workflow runs (conversations) within date range.
        Workflow runs are tracked via conversations since each conversation
        typically triggers a workflow execution.
        """
        query = select(func.count(ConversationModel.id)).where(
            ConversationModel.is_deleted == 0
        )

        if from_date:
            query = query.where(ConversationModel.conversation_date >= from_date)
        if to_date:
            query = query.where(ConversationModel.conversation_date <= to_date)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_avg_response_time(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> int:
        """Get average response time in milliseconds from the pre-aggregated daily stats.

        Reads the twice-daily aggregated agent_execution_daily_stats table instead of
        recomputing from raw transcript messages on every request. Days are combined as
        an execution-count-weighted average, matching the analytics summary convention.
        """
        weighted_sum = func.sum(
            AgentExecutionDailyStatsModel.avg_response_ms
            * AgentExecutionDailyStatsModel.execution_count
        )
        total_executions = func.sum(AgentExecutionDailyStatsModel.execution_count)

        query = select(
            weighted_sum / func.nullif(total_executions, 0)
        ).where(AgentExecutionDailyStatsModel.is_deleted == 0)

        if from_date:
            query = query.where(AgentExecutionDailyStatsModel.stat_date >= from_date)
        if to_date:
            query = query.where(AgentExecutionDailyStatsModel.stat_date <= to_date)

        result = await self.db.execute(query)
        avg = result.scalar()
        return int(avg) if avg else 0

    async def get_active_conversations(
        self,
        limit: int = 10,
        offset: int = 0,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> list[ConversationModel]:
        """Get active (in-progress and takeover) conversations with their analysis and messages."""
        query = (
            select(ConversationModel)
            .where(
                ConversationModel.is_deleted == 0,
                ConversationModel.status.in_(["in_progress", "takeover"])
            )
            .options(
                selectinload(ConversationModel.analysis),
                selectinload(ConversationModel.messages),
                selectinload(ConversationModel.operator).selectinload(OperatorModel.agent),
            )
            .order_by(ConversationModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        if from_date:
            query = query.where(ConversationModel.conversation_date >= from_date)
        if to_date:
            query = query.where(ConversationModel.conversation_date <= to_date)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_conversation_feedback_counts(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> dict:
        """Get counts of conversations by sentiment derived from hostility score.

        Thresholds (matching frontend):
        - good (positive): hostility_score <= 20
        - neutral: hostility_score > 20 AND <= 49
        - bad (negative): hostility_score > 49
        """
        # Hostility thresholds (must match frontend constants)
        HOSTILITY_POSITIVE_MAX = 20
        HOSTILITY_NEUTRAL_MAX = 49

        # Handle NULL hostility scores as 0 (positive/good)
        hostility_score = func.coalesce(ConversationModel.in_progress_hostility_score, 0)

        query = select(
            func.count(case((hostility_score <= HOSTILITY_POSITIVE_MAX, 1))).label("good_count"),
            func.count(case((
                and_(
                    hostility_score > HOSTILITY_POSITIVE_MAX,
                    hostility_score <= HOSTILITY_NEUTRAL_MAX
                ), 1
            ))).label("neutral_count"),
            func.count(case((hostility_score > HOSTILITY_NEUTRAL_MAX, 1))).label("bad_count"),
            func.count(ConversationModel.id).label("total")
        ).where(
            ConversationModel.is_deleted == 0,
            ConversationModel.status.in_(["in_progress", "takeover"])
        )

        if from_date:
            query = query.where(ConversationModel.conversation_date >= from_date)
        if to_date:
            query = query.where(ConversationModel.conversation_date <= to_date)

        group_clause = get_group_scope_clause(ConversationModel)
        if group_clause is not None:
            query = query.where(group_clause)

        result = await self.db.execute(query)
        row = result.first()

        return {
            "good_count": row.good_count if row else 0,
            "bad_count": row.bad_count if row else 0,
            "neutral_count": row.neutral_count if row else 0,
            "total": row.total if row else 0
        }

    async def get_agents_with_stats(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Load a short list of agents and their stats for the dashboard"""
        # Get agents with their operators and statistics
        query = (
            select(AgentModel)
            .where(AgentModel.is_deleted == 0)
            .options(
                selectinload(AgentModel.operator).selectinload(OperatorModel.operator_statistics)
            )
            .order_by(AgentModel.name)
            .limit(limit)
        )

        result = await self.db.execute(query)
        agents = list(result.scalars().all())

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        agent_ids = [a.id for a in agents]
        cost_by_agent = await self._agent_cost_today(agent_ids, today_start, today_end)

        # Fetch today's conversation counts for all operators in a single GROUP BY query
        operator_ids = [a.operator_id for a in agents if a.operator_id]
        conv_count_by_operator: dict = {}
        if operator_ids:
            conv_count_query = (
                select(
                    ConversationModel.operator_id,
                    func.count(ConversationModel.id).label("count"),
                )
                .where(
                    ConversationModel.operator_id.in_(operator_ids),
                    ConversationModel.is_deleted == 0,
                    ConversationModel.conversation_date >= today_start,
                )
                .group_by(ConversationModel.operator_id)
            )
            conv_count_result = await self.db.execute(conv_count_query)
            conv_count_by_operator = {row.operator_id: row.count for row in conv_count_result.all()}

        # Fetch avg response times per agent from the pre-aggregated daily stats.
        # agent <-> operator is 1:1 (AgentModel.operator_id is unique), and the
        # daily-stats table is keyed by agent_id, so we look up by agent.id.
        avg_response_by_agent = await self._calculate_response_times_for_agents(
            [a.id for a in agents], from_date=from_date, to_date=to_date
        )

        agent_stats = []
        for agent in agents:
            operator_stats = (
                agent.operator.operator_statistics
                if agent.operator and agent.operator.operator_statistics
                else None
            )
            cost_record = cost_by_agent.get(agent.id) or {}
            agent_stats.append({
                "id": agent.id,
                "name": agent.name,
                "is_active": agent.is_active == 1,
                "conversations_today": conv_count_by_operator.get(agent.operator_id, 0),
                "resolution_rate": operator_stats.avg_resolution_rate if operator_stats else 0,
                "avg_response_time_ms": avg_response_by_agent.get(agent.id, 0),
                "cost": cost_record.get("cost"),
                "cost_per_conversation": cost_record.get("cost_per_conversation"),
            })

        return agent_stats

    async def _agent_cost_today(
        self, agent_ids: list[UUID], day_start: datetime, day_end: datetime
    ) -> dict[UUID, dict]:
        """Today's per-agent cost and cost-per-conversation from the usage ledger"""
        if not agent_ids:
            return {}
        conversation_cost = func.coalesce(
            func.sum(LlmUsageEventModel.cost_usd).filter(LlmUsageEventModel.conversation_id.isnot(None)),
            0,
        )
        query = (
            select(
                LlmUsageEventModel.agent_id,
                func.coalesce(func.sum(LlmUsageEventModel.cost_usd), 0).label("cost_usd"),
                conversation_cost.label("conversation_cost_usd"),
                func.count(distinct(LlmUsageEventModel.conversation_id)).label("distinct_conversations"),
            )
            .where(
                LlmUsageEventModel.is_deleted == 0,
                LlmUsageEventModel.agent_id.in_(agent_ids),
                LlmUsageEventModel.occurred_at >= day_start,
                LlmUsageEventModel.occurred_at < day_end,
            )
            .group_by(LlmUsageEventModel.agent_id)
        )
        result = await self.db.execute(query)
        cost_by_agent: dict[UUID, dict] = {}
        for row in result.all():
            conversations = row.distinct_conversations or 0
            cost_by_agent[row.agent_id] = {
                "cost": float(row.cost_usd or 0),
                "cost_per_conversation": (
                    float(row.conversation_cost_usd) / conversations if conversations else None
                ),
            }
        return cost_by_agent

    async def _calculate_response_times_for_agents(
        self,
        agent_ids: list[UUID],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict[UUID, int]:
        """Average response time per agent from the pre-aggregated daily stats.

        Reads agent_execution_daily_stats (populated by the twice-daily Celery job)
        instead of recomputing from raw transcript messages. Days are combined as an
        execution-count-weighted average, matching the analytics summary convention.
        """
        if not agent_ids:
            return {}

        weighted_sum = func.sum(
            AgentExecutionDailyStatsModel.avg_response_ms
            * AgentExecutionDailyStatsModel.execution_count
        )
        total_executions = func.sum(AgentExecutionDailyStatsModel.execution_count)

        query = (
            select(
                AgentExecutionDailyStatsModel.agent_id,
                (weighted_sum / func.nullif(total_executions, 0)).label("avg_ms"),
            )
            .where(
                AgentExecutionDailyStatsModel.agent_id.in_(agent_ids),
                AgentExecutionDailyStatsModel.is_deleted == 0,
            )
            .group_by(AgentExecutionDailyStatsModel.agent_id)
        )

        if from_date:
            query = query.where(AgentExecutionDailyStatsModel.stat_date >= from_date)
        if to_date:
            query = query.where(AgentExecutionDailyStatsModel.stat_date <= to_date)

        result = await self.db.execute(query)
        return {
            row.agent_id: int(row.avg_ms)
            for row in result.all()
            if row.avg_ms is not None
        }

    async def get_active_integrations(self) -> list[AppSettingsModel]:
        """Get all active integrations (app settings)."""
        query = (
            select(AppSettingsModel)
            .where(
                AppSettingsModel.is_deleted == 0,
                AppSettingsModel.is_active == 1
            )
            .order_by(AppSettingsModel.type, AppSettingsModel.name)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_total_cost_usd(self, from_date: datetime, to_date: datetime) -> float:
        """Total priced LLM cost over the range from the usage ledger"""
        window_start, window_end = _ledger_window(from_date, to_date)
        query = select(func.coalesce(func.sum(LlmUsageEventModel.cost_usd), 0)).where(
            LlmUsageEventModel.is_deleted == 0,
            LlmUsageEventModel.occurred_at >= window_start,
            LlmUsageEventModel.occurred_at < window_end,
        )
        result = await self.db.execute(query)
        return float(result.scalar() or 0.00)
