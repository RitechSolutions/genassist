import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.schemas.dashboard import (
    ActiveConversationsResponse,
    AgentStatsResponse,
    DashboardResponse,
    DashboardSummaryStats,
    IntegrationsResponse,
)
from app.schemas.notification import NotificationFeedResponse
from app.services.dashboard import DashboardService
from app.services.notification_feed import NotificationFeedService

logger = logging.getLogger(__name__)
router = APIRouter()


def parse_date_range(days: int = 30) -> tuple[datetime, datetime]:
    """Parse days parameter into date range."""
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=days)
    return from_date, to_date


@router.get(
    "",
    response_model=DashboardResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get full dashboard data",
    description="Returns all dashboard sections: summary stats, active conversations, agents, and integrations.",
)
async def get_dashboard(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back for statistics"),
    conversations_page: int = Query(default=1, ge=1, description="Page number for active conversations"),
    conversations_page_size: int = Query(default=3, ge=1, le=100, description="Number of active conversations per page"),
    agents_limit: int = Query(default=5, ge=1, le=100, description="Maximum number of agents to return"),
    dashboard_service: DashboardService = Injected(DashboardService),
) -> DashboardResponse:
    """
    Get complete dashboard data including:
    - Summary statistics (active agents, workflow runs, avg response time)
    - Active conversations with feedback counts (paginated)
    - Agent statistics (conversations today, resolution rate, etc.)
    - Active integrations
    """
    return await dashboard_service.get_full_dashboard(
        days=days,
        conversations_page=conversations_page,
        conversations_page_size=conversations_page_size,
        agents_limit=agents_limit
    )


@router.get(
    "/summary",
    response_model=DashboardSummaryStats,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get dashboard summary statistics",
    description="Returns summary statistics: active agents count, workflow runs, and average response time.",
)
async def get_summary_stats(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    dashboard_service: DashboardService = Injected(DashboardService),
) -> DashboardSummaryStats:
    """
    Get dashboard summary statistics:
    - Number of active agents
    - Total workflow runs in the period
    - Average response time in milliseconds
    - Total cost in USD
    """
    from_date, to_date = parse_date_range(days)
    return await dashboard_service.get_summary_stats(from_date, to_date)


@router.get(
    "/conversations",
    response_model=ActiveConversationsResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get active conversations",
    description="Returns active (in-progress) conversations with feedback breakdown and pagination.",
)
async def get_active_conversations(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Number of conversations per page"),
    dashboard_service: DashboardService = Injected(DashboardService),
) -> ActiveConversationsResponse:
    """
    Get active conversations section:
    - List of in-progress conversations (paginated)
    - Count by feedback type (Good, Neutral, Bad)
    - Total count of active conversations
    - Pagination info (page, page_size, has_more)
    """
    from_date, to_date = parse_date_range(days)
    return await dashboard_service.get_active_conversations(
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date
    )


@router.get(
    "/agents",
    response_model=AgentStatsResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get agents with statistics",
    description="Returns agents with their performance statistics (limited for dashboard display).",
)
async def get_agents_stats(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(default=5, ge=1, le=100, description="Maximum number of agents to return"),
    dashboard_service: DashboardService = Injected(DashboardService),
) -> AgentStatsResponse:
    """
    Get agents with their statistics:
    - Conversations today
    - Resolution rate
    - Average response time
    - Cost (if available)
    """
    from_date, to_date = parse_date_range(days)
    return await dashboard_service.get_agents_stats(from_date, to_date, limit=limit)


@router.get(
    "/integrations",
    response_model=IntegrationsResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get active integrations",
    description="Returns all active integrations (Zendesk, Gmail, Slack, etc.).",
)
async def get_integrations(
    dashboard_service: DashboardService = Injected(DashboardService),
) -> IntegrationsResponse:
    """
    Get active integrations:
    - Email (Gmail)
    - Zendesk
    - Slack
    - WhatsApp
    - Calendar
    - Other configured integrations
    """
    return await dashboard_service.get_integrations()


@router.get(
    "/notifications",
    response_model=NotificationFeedResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get notification feed",
    description="Returns recent notification candidates from real backend events.",
)
async def get_notifications(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of notifications"),
    skip: int = Query(default=0, ge=0, le=10_000, description="Offset into the merged feed"),
    notification_type: Literal[
        "all",
        "conversation_started",
        "conversation_hostility",
        "conversation_finalized_hostility",
    ] = Query(
        default="all",
        description="Server-side type filter for notification categories.",
    ),
    include_conversation_started: bool = Query(
        default=True,
        description="When false, omits conversation-started rows from the feed (pagination-stable).",
    ),
    include_conversation_hostility: bool = Query(
        default=True,
        description="When false, omits high-hostility notifications.",
    ),
    include_conversation_finalized_hostility: bool = Query(
        default=True,
        description="When false, omits finalized high-hostility notifications.",
    ),
    include_workflow_failed: bool = Query(
        default=True,
        description="When false, omits workflow failed notifications.",
    ),
    notification_feed_service: NotificationFeedService = Injected(NotificationFeedService),
) -> NotificationFeedResponse:
    if not hasattr(request.state, "user") or not request.state.user:
        raise AppException(status_code=401, error_key=ErrorKey.NOT_AUTHENTICATED)
    user = request.state.user
    gid = getattr(user, "group_id", None)
    supervised = list(getattr(user, "supervised_group_ids", None) or [])
    items, has_more = await notification_feed_service.get_feed(
        user_id=user.id,
        user_group_id=gid,
        supervised_group_ids=supervised,
        limit=limit,
        skip=skip,
        include_conversation_started=include_conversation_started,
        include_conversation_hostility=include_conversation_hostility,
        include_conversation_finalized_hostility=include_conversation_finalized_hostility,
        include_workflow_failed=include_workflow_failed,
        notification_type=notification_type,
    )
    return NotificationFeedResponse(items=items, has_more=has_more)
