import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.dashboard import (
    DashboardSummaryStats,
    ActiveConversationsResponse,
    AgentStatsResponse,
    IntegrationsResponse,
    DashboardResponse,
)
from app.services.dashboard import DashboardService

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
        conversations_page_size=conversations_page_size
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
    description="Returns all agents with their performance statistics.",
)
async def get_agents_stats(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
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
    return await dashboard_service.get_agents_stats(from_date, to_date)


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
