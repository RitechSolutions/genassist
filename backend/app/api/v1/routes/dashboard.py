import logging
from datetime import datetime, timedelta, timezone
from typing import Literal, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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


DEFAULT_SUMMARY_DAYS = 30


class SummaryRange(NamedTuple):
    """Resolved summary bounds"""
    from_date: datetime | None
    to_date: datetime | None
    exact: bool


def parse_date_range(days: int = 30) -> tuple[datetime, datetime]:
    """Parse days parameter into date range."""
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=days)
    return from_date, to_date


def resolve_summary_range(
    days: int | None,
    from_datetime: datetime | None,
    to_datetime: datetime | None,
    all_time: bool,
) -> SummaryRange:
    """Resolve the summary range into bounds, rejecting mixed modes with a 422"""
    has_exact_boundary = from_datetime is not None or to_datetime is not None

    if all_time:
        if days is not None or has_exact_boundary:
            raise HTTPException(
                status_code=422,
                detail="all_time cannot be combined with days, from_datetime or to_datetime",
            )
        return SummaryRange(None, None, exact=False)

    if has_exact_boundary:
        if days is not None:
            raise HTTPException(
                status_code=422,
                detail="days cannot be combined with from_datetime or to_datetime",
            )
        if from_datetime is None or to_datetime is None:
            raise HTTPException(
                status_code=422,
                detail="from_datetime and to_datetime must be supplied together",
            )
        if from_datetime.utcoffset() is None or to_datetime.utcoffset() is None:
            raise HTTPException(
                status_code=422,
                detail="from_datetime and to_datetime must include a timezone offset",
            )
        if from_datetime >= to_datetime:
            raise HTTPException(
                status_code=422,
                detail="from_datetime must be earlier than to_datetime",
            )
        return SummaryRange(from_datetime, to_datetime, exact=True)

    rolling_from, rolling_to = parse_date_range(days if days is not None else DEFAULT_SUMMARY_DAYS)
    return SummaryRange(rolling_from, rolling_to, exact=False)


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
    - Summary statistics (active agents, conversations with agent activity, avg response time)
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
    description=(
        "Returns summary statistics: active agents count, conversations with agent activity, "
        "and average response time."
    ),
)
async def get_summary_stats(
    days: int | None = Query(
        default=None,
        ge=1,
        le=365,
        description="Number of days to look back, defaults to 30 when no other range is supplied",
    ),
    from_datetime: datetime | None = Query(
        default=None,
        description="Inclusive start of an exact range, requires to_datetime and a timezone offset",
    ),
    to_datetime: datetime | None = Query(
        default=None,
        description="Exclusive end of an exact range, requires from_datetime and a timezone offset",
    ),
    all_time: bool = Query(
        default=False,
        description="Drop all date filtering, cannot be combined with days or an exact boundary",
    ),
    dashboard_service: DashboardService = Injected(DashboardService),
) -> DashboardSummaryStats:
    """
    Get dashboard summary statistics:
    - Number of active agents
    - Conversations with agent activity in the period
    - Average response time in milliseconds
    - Total cost in USD
    """
    summary_range = resolve_summary_range(days, from_datetime, to_datetime, all_time)
    return await dashboard_service.get_summary_stats(
        summary_range.from_date, summary_range.to_date, exact=summary_range.exact
    )


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
    description="Returns recent notifications for the authenticated user.",
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
        "workflow_failed",
    ] = Query(
        default="all",
        description="Server-side type filter for persisted notification categories.",
    ),
    notification_level: Literal["all", "info", "success", "warning", "error"] = Query(
        default="all",
        description="Server-side severity filter for persisted notifications.",
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
    items, has_more, unread_count = await notification_feed_service.get_feed(
        user_id=user.id,
        limit=limit,
        skip=skip,
        include_conversation_started=include_conversation_started,
        include_conversation_hostility=include_conversation_hostility,
        include_conversation_finalized_hostility=include_conversation_finalized_hostility,
        include_workflow_failed=include_workflow_failed,
        notification_type=notification_type,
        notification_level=notification_level,
    )
    return NotificationFeedResponse(
        items=items,
        has_more=has_more,
        unread_count=unread_count,
    )
