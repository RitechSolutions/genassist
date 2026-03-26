from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from injector import inject
from sqlalchemy import and_, case, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import aliased, selectinload

from app.db.models.agent import AgentModel
from app.db.models.agent_execution_daily_stats import AgentExecutionDailyStatsModel
from app.db.models.app_settings import AppSettingsModel
from app.db.models.conversation import ConversationModel
from app.db.models.message_model import TranscriptMessageModel
from app.db.models.operator import OperatorModel


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
        """Get average response time in milliseconds calculated from message timestamps.

        Calculates the actual time between customer messages and agent responses
        by analyzing consecutive message pairs entirely in SQL.
        """
        m1 = aliased(TranscriptMessageModel, name="m1")
        m2 = aliased(TranscriptMessageModel, name="m2")

        query = (
            select(func.avg((m2.start_time - m1.end_time) * 1000))
            .select_from(m1)
            .join(m2, and_(
                m2.conversation_id == m1.conversation_id,
                m2.sequence_number == m1.sequence_number + 1,
                m2.start_time >= m1.end_time,
            ))
            .join(ConversationModel, ConversationModel.id == m1.conversation_id)
            .where(
                ConversationModel.is_deleted == 0,
                or_(m1.speaker.ilike("%customer%"), func.lower(m1.speaker) == "speaker_00"),
                or_(m2.speaker.ilike("%agent%"), func.lower(m2.speaker) == "speaker_01"),
            )
        )

        if from_date:
            query = query.where(ConversationModel.conversation_date >= from_date)
        if to_date:
            query = query.where(ConversationModel.conversation_date <= to_date)

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
                selectinload(ConversationModel.messages)
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
        limit: int = 5
    ) -> list[dict]:
        """Get agents with their statistics (limited for dashboard display)."""
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
        today_date = today_start.date()

        # Fetch today's cost per agent in a single query
        cost_query = (
            select(
                AgentExecutionDailyStatsModel.agent_id,
                func.coalesce(AgentExecutionDailyStatsModel.total_cost_usd, 0).label("cost_usd"),
            )
            .where(
                AgentExecutionDailyStatsModel.stat_date == today_date,
                AgentExecutionDailyStatsModel.is_deleted == 0,
                AgentExecutionDailyStatsModel.agent_id.in_([a.id for a in agents]),
            )
        )
        cost_result = await self.db.execute(cost_query)
        cost_by_agent = {row.agent_id: float(row.cost_usd or 0) for row in cost_result.all()}

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

        # Fetch avg response times for all operators in a single query
        avg_response_by_operator = await self._calculate_response_times_for_operators(operator_ids)

        agent_stats = []
        for agent in agents:
            operator_stats = (
                agent.operator.operator_statistics
                if agent.operator and agent.operator.operator_statistics
                else None
            )
            agent_stats.append({
                "id": agent.id,
                "name": agent.name,
                "is_active": agent.is_active == 1,
                "conversations_today": conv_count_by_operator.get(agent.operator_id, 0),
                "resolution_rate": operator_stats.avg_resolution_rate if operator_stats else 0,
                "avg_response_time_ms": avg_response_by_operator.get(agent.operator_id, 0),
                "cost": cost_by_agent.get(agent.id, 0.0),
            })

        return agent_stats

    async def _calculate_response_times_for_operators(
        self, operator_ids: list[UUID]
    ) -> dict[UUID, int]:
        """Calculate average response time per operator in a single SQL query."""
        if not operator_ids:
            return {}

        m1 = aliased(TranscriptMessageModel, name="m1")
        m2 = aliased(TranscriptMessageModel, name="m2")

        query = (
            select(
                ConversationModel.operator_id,
                func.avg((m2.start_time - m1.end_time) * 1000).label("avg_ms"),
            )
            .select_from(m1)
            .join(m2, and_(
                m2.conversation_id == m1.conversation_id,
                m2.sequence_number == m1.sequence_number + 1,
                m2.start_time >= m1.end_time,
            ))
            .join(ConversationModel, ConversationModel.id == m1.conversation_id)
            .where(
                ConversationModel.operator_id.in_(operator_ids),
                ConversationModel.is_deleted == 0,
                or_(m1.speaker.ilike("%customer%"), func.lower(m1.speaker) == "speaker_00"),
                or_(m2.speaker.ilike("%agent%"), func.lower(m2.speaker) == "speaker_01"),
            )
            .group_by(ConversationModel.operator_id)
        )

        result = await self.db.execute(query)
        return {
            row.operator_id: int(row.avg_ms)
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

    async def get_total_cost_usd(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> float:
        """Get total cost in USD for the given date range."""
        query = select(func.sum(AgentExecutionDailyStatsModel.total_cost_usd)).where(
            AgentExecutionDailyStatsModel.stat_date >= from_date,
            AgentExecutionDailyStatsModel.stat_date <= to_date,
            AgentExecutionDailyStatsModel.is_deleted == 0
        )
        result = await self.db.execute(query)
        return float(result.scalar() or 0.00)
