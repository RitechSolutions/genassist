import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from injector import inject

from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import (
    DashboardSummaryStats,
    ActiveConversationItem,
    ActiveConversationsResponse,
    AgentStatsItem,
    AgentStatsResponse,
    IntegrationItem,
    IntegrationsResponse,
    DashboardResponse,
)


logger = logging.getLogger(__name__)


# Integration type to description mapping
INTEGRATION_DESCRIPTIONS = {
    "Zendesk": "Create support tickets",
    "Gmail": "Send via Gmail",
    "WhatsApp": "Send WhatsApp messages",
    "Slack": "Send Slack messages",
    "Microsoft": "Microsoft 365 integration",
    "Jira": "Create Jira issues",
    "Other": "Custom integration",
}


@inject
class DashboardService:

    def __init__(self, dashboard_repo: DashboardRepository):
        self.dashboard_repo = dashboard_repo

    def _get_date_range(self, days: int = 30) -> tuple[datetime, datetime]:
        """Get date range from now going back specified days."""
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=days)
        return from_date, to_date

    async def get_summary_stats(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> DashboardSummaryStats:
        """Get summary statistics for the dashboard header."""
        active_agents = await self.dashboard_repo.get_active_agents_count()
        workflow_runs = await self.dashboard_repo.get_workflow_runs_count(from_date, to_date)
        avg_response_time = await self.dashboard_repo.get_avg_response_time(from_date, to_date)

        return DashboardSummaryStats(
            active_agents=active_agents,
            workflow_runs=workflow_runs,
            avg_response_time_ms=avg_response_time
        )

    async def get_active_conversations(
        self,
        page: int = 1,
        page_size: int = 10,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> ActiveConversationsResponse:
        """Get active conversations section data with pagination."""
        offset = (page - 1) * page_size

        conversations = await self.dashboard_repo.get_active_conversations(
            limit=page_size,
            offset=offset,
            from_date=from_date,
            to_date=to_date
        )
        feedback_counts = await self.dashboard_repo.get_conversation_feedback_counts(
            from_date=from_date,
            to_date=to_date
        )

        conversation_items = []
        for conv in conversations:
            # Get last message text - format as "Speaker: message"
            last_message = None
            if conv.messages and len(conv.messages) > 0:
                last_msg = conv.messages[-1]
                speaker = getattr(last_msg, 'speaker', None) or 'Agent'
                text = getattr(last_msg, 'text', '') or ''
                if speaker and text:
                    last_message = f"{speaker.capitalize()}: {text}"
                elif text:
                    last_message = text

            # Get topic from conversation or analysis
            topic = conv.topic
            if not topic and conv.analysis:
                topic = conv.analysis.topic

            conversation_items.append(ActiveConversationItem(
                id=conv.id,
                topic=topic,
                feedback=conv.feedback,
                duration=conv.duration or 0,
                last_message=last_message,
                status=conv.status,
                created_at=conv.created_at,
                negative_reason=conv.negative_reason,
                in_progress_hostility_score=conv.in_progress_hostility_score or 0
            ))

        total = feedback_counts["total"]
        has_more = (offset + len(conversation_items)) < total

        return ActiveConversationsResponse(
            total=total,
            good_count=feedback_counts["good_count"],
            neutral_count=feedback_counts["neutral_count"],
            bad_count=feedback_counts["bad_count"],
            conversations=conversation_items,
            page=page,
            page_size=page_size,
            has_more=has_more
        )

    async def get_agents_stats(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> AgentStatsResponse:
        """Get agents with their statistics."""
        agent_stats = await self.dashboard_repo.get_agents_with_stats(
            from_date=from_date,
            to_date=to_date
        )

        agent_items = [
            AgentStatsItem(
                id=agent["id"],
                name=agent["name"],
                conversations_today=agent["conversations_today"],
                resolution_rate=Decimal(str(agent["resolution_rate"])) if agent["resolution_rate"] else Decimal("0.00"),
                avg_response_time_ms=agent["avg_response_time_ms"],
                cost=Decimal(str(agent["cost"])) if agent["cost"] else Decimal("0.00"),
                is_active=agent["is_active"]
            )
            for agent in agent_stats
        ]

        return AgentStatsResponse(agents=agent_items)

    async def get_integrations(self) -> IntegrationsResponse:
        """Get active integrations."""
        integrations = await self.dashboard_repo.get_active_integrations()

        integration_items = [
            IntegrationItem(
                id=integration.id,
                name=integration.name,
                type=integration.type,
                description=integration.description or INTEGRATION_DESCRIPTIONS.get(
                    integration.type, "Custom integration"
                ),
                is_active=integration.is_active == 1
            )
            for integration in integrations
        ]

        return IntegrationsResponse(integrations=integration_items)

    async def get_full_dashboard(
        self,
        days: int = 30,
        conversations_page: int = 1,
        conversations_page_size: int = 3
    ) -> DashboardResponse:
        """Get complete dashboard data."""
        from_date, to_date = self._get_date_range(days)

        summary = await self.get_summary_stats(from_date, to_date)
        active_conversations = await self.get_active_conversations(
            page=conversations_page,
            page_size=conversations_page_size,
            from_date=from_date,
            to_date=to_date
        )
        agents = await self.get_agents_stats(from_date, to_date)
        integrations = await self.get_integrations()

        return DashboardResponse(
            summary=summary,
            active_conversations=active_conversations,
            agents=agents,
            integrations=integrations
        )
