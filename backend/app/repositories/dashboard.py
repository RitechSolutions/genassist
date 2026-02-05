from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from injector import inject
from sqlalchemy import func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel
from app.db.models.operator import OperatorModel, OperatorStatisticsModel
from app.db.models.app_settings import AppSettingsModel


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
        by analyzing message pairs within conversations.
        """
        # Get conversations with their messages
        query = (
            select(ConversationModel)
            .where(ConversationModel.is_deleted == 0)
            .options(selectinload(ConversationModel.messages))
        )

        if from_date:
            query = query.where(ConversationModel.conversation_date >= from_date)
        if to_date:
            query = query.where(ConversationModel.conversation_date <= to_date)

        result = await self.db.execute(query)
        conversations = list(result.scalars().all())

        response_times = []
        for conv in conversations:
            if not conv.messages or len(conv.messages) < 2:
                continue

            # Sort messages by sequence number to ensure correct order
            sorted_messages = sorted(conv.messages, key=lambda m: m.sequence_number)

            # Find pairs where customer message is followed by agent message
            for i in range(len(sorted_messages) - 1):
                current_msg = sorted_messages[i]
                next_msg = sorted_messages[i + 1]

                # Check if current is customer and next is agent
                # Speaker can be "customer", "SPEAKER_00", etc. for customer
                # and "agent", "SPEAKER_01", etc. for agent
                current_speaker = current_msg.speaker.lower() if current_msg.speaker else ""
                next_speaker = next_msg.speaker.lower() if next_msg.speaker else ""

                is_customer_msg = "customer" in current_speaker or current_speaker == "speaker_00"
                is_agent_msg = "agent" in next_speaker or next_speaker == "speaker_01"

                if is_customer_msg and is_agent_msg:
                    # Calculate response time using start_time (seconds from conversation start)
                    # start_time of agent message - end_time of customer message
                    response_time_seconds = next_msg.start_time - current_msg.end_time
                    if response_time_seconds >= 0:
                        response_times.append(response_time_seconds * 1000)  # Convert to ms

        if not response_times:
            return 0

        return int(sum(response_times) / len(response_times))

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
        to_date: Optional[datetime] = None
    ) -> list[dict]:
        """Get all agents with their statistics."""
        # Get agents with their operators and statistics
        query = (
            select(AgentModel)
            .where(AgentModel.is_deleted == 0)
            .options(
                selectinload(AgentModel.operator).selectinload(OperatorModel.operator_statistics)
            )
            .order_by(AgentModel.name)
        )

        result = await self.db.execute(query)
        agents = list(result.scalars().all())

        # Get conversation counts per agent for today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        agent_stats = []
        for agent in agents:
            # Get conversation count for this agent's operator
            conv_count_query = select(func.count(ConversationModel.id)).where(
                ConversationModel.operator_id == agent.operator_id,
                ConversationModel.is_deleted == 0,
                ConversationModel.conversation_date >= today_start
            )
            conv_result = await self.db.execute(conv_count_query)
            conversations_today = conv_result.scalar() or 0

            # Get stats from operator statistics
            operator_stats = (
                agent.operator.operator_statistics
                if agent.operator and agent.operator.operator_statistics
                else None
            )

            # Calculate actual response time from messages for this agent
            avg_response_time_ms = await self._calculate_agent_response_time(agent.operator_id)

            agent_stats.append({
                "id": agent.id,
                "name": agent.name,
                "is_active": agent.is_active == 1,
                "conversations_today": conversations_today,
                "resolution_rate": operator_stats.avg_resolution_rate if operator_stats else 0,
                "avg_response_time_ms": avg_response_time_ms,
                "cost": 0  # Cost calculation would depend on LLM usage tracking
            })

        return agent_stats

    async def _calculate_agent_response_time(self, operator_id: UUID) -> int:
        """Calculate average response time for a specific agent/operator from message timestamps."""
        # Get recent conversations for this operator with messages
        query = (
            select(ConversationModel)
            .where(
                ConversationModel.operator_id == operator_id,
                ConversationModel.is_deleted == 0
            )
            .options(selectinload(ConversationModel.messages))
            .limit(100)  # Limit to recent conversations for performance
        )

        result = await self.db.execute(query)
        conversations = list(result.scalars().all())

        response_times = []
        for conv in conversations:
            if not conv.messages or len(conv.messages) < 2:
                continue

            sorted_messages = sorted(conv.messages, key=lambda m: m.sequence_number)

            for i in range(len(sorted_messages) - 1):
                current_msg = sorted_messages[i]
                next_msg = sorted_messages[i + 1]

                current_speaker = current_msg.speaker.lower() if current_msg.speaker else ""
                next_speaker = next_msg.speaker.lower() if next_msg.speaker else ""

                is_customer_msg = "customer" in current_speaker or current_speaker == "speaker_00"
                is_agent_msg = "agent" in next_speaker or next_speaker == "speaker_01"

                if is_customer_msg and is_agent_msg:
                    response_time_seconds = next_msg.start_time - current_msg.end_time
                    if response_time_seconds >= 0:
                        response_times.append(response_time_seconds * 1000)

        if not response_times:
            return 0

        return int(sum(response_times) / len(response_times))

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
