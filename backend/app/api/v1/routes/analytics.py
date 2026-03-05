import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.schemas.analytics import (
    AgentDailyStatsListResponse,
    AgentStatsSummaryResponse,
    NodeDailyStatsListResponse,
    NodeTypeBreakdownResponse,
)
from app.services.analytics_read import AnalyticsReadService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/agents",
    response_model=AgentDailyStatsListResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get daily agent execution stats",
)
async def get_agent_daily_stats(
    agent_id: UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    service: AnalyticsReadService = Injected(AnalyticsReadService),
) -> AgentDailyStatsListResponse:
    return await service.get_agent_daily_stats(
        agent_id=agent_id, from_date=from_date, to_date=to_date
    )


@router.get(
    "/agents/summary",
    response_model=AgentStatsSummaryResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get aggregated agent stats summary across a date range",
)
async def get_agent_stats_summary(
    agent_id: UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    service: AnalyticsReadService = Injected(AnalyticsReadService),
) -> AgentStatsSummaryResponse:
    return await service.get_agent_stats_summary(
        agent_id=agent_id, from_date=from_date, to_date=to_date
    )


@router.get(
    "/nodes",
    response_model=NodeDailyStatsListResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get daily node execution stats",
)
async def get_node_daily_stats(
    agent_id: UUID | None = Query(default=None),
    node_type: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    service: AnalyticsReadService = Injected(AnalyticsReadService),
) -> NodeDailyStatsListResponse:
    return await service.get_node_daily_stats(
        agent_id=agent_id, node_type=node_type, from_date=from_date, to_date=to_date
    )


@router.get(
    "/agents/{agent_id}/nodes/breakdown",
    response_model=NodeTypeBreakdownResponse,
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get node type breakdown for a specific agent",
)
async def get_node_type_breakdown(
    agent_id: UUID,
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    service: AnalyticsReadService = Injected(AnalyticsReadService),
) -> NodeTypeBreakdownResponse:
    return await service.get_node_type_breakdown(
        agent_id=agent_id, from_date=from_date, to_date=to_date
    )
