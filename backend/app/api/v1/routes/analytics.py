import io
import logging
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.repositories.agent import AgentRepository
from app.schemas.analytics import (
    AgentDailyStatsListResponse,
    AgentStatsSummaryResponse,
    NodeDailyStatsListResponse,
    NodeTypeBreakdownResponse,
)
from app.services.analytics_export import EXTENSIONS, VALID_FORMATS, export_agent_stats, export_node_stats, get_agent_names
from app.services.analytics_read import AnalyticsReadService
from app.services.audio import AudioService

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
    compare: bool = Query(default=False),
    service: AnalyticsReadService = Injected(AnalyticsReadService),
):
    if compare:
        return await service.get_agent_stats_summary_with_comparison(
            agent_id=agent_id, from_date=from_date, to_date=to_date
        )
    return await service.get_agent_stats_summary(
        agent_id=agent_id, from_date=from_date, to_date=to_date
    )


@router.get(
    "/agents/export",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Export agent performance report (csv / xlsx / pdf)",
)
async def export_agent_performance(
    fmt: str = Query(default="csv", alias="format"),
    agent_id: UUID | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    service: AnalyticsReadService = Injected(AnalyticsReadService),
    agent_repo: AgentRepository = Injected(AgentRepository),
) -> StreamingResponse:
    if fmt not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of: {', '.join(sorted(VALID_FORMATS))}")

    try:
        summary, daily = await _fetch_agent_data(service, agent_id, from_date, to_date)
        agent_names = await get_agent_names(agent_repo)

        node_breakdown = None
        if agent_id is not None:
            nb = await service.get_node_type_breakdown(agent_id=agent_id, from_date=from_date, to_date=to_date)
            node_breakdown = nb.items

        content, media_type = export_agent_stats(
            fmt=fmt,
            summary=summary,
            items=daily.items,
            agent_id=str(agent_id) if agent_id else None,
            agent_names=agent_names,
            from_date=from_date,
            to_date=to_date,
            node_breakdown=node_breakdown,
        )
    except Exception as exc:
        logger.exception("Agent export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    return _build_streaming_response(content, media_type, "agent-performance", fmt)


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
    "/nodes/export",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Export node analytics report (csv / xlsx / pdf)",
)
async def export_node_analytics(
    fmt: str = Query(default="csv", alias="format"),
    agent_id: UUID | None = Query(default=None),
    node_type: str | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    service: AnalyticsReadService = Injected(AnalyticsReadService),
    agent_repo: AgentRepository = Injected(AgentRepository),
) -> StreamingResponse:
    if fmt not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of: {', '.join(sorted(VALID_FORMATS))}")

    try:
        daily = await service.get_node_daily_stats(
            agent_id=agent_id, node_type=node_type, from_date=from_date, to_date=to_date
        )
        agent_names = await get_agent_names(agent_repo)

        content, media_type = export_node_stats(
            fmt=fmt,
            items=daily.items,
            agent_names=agent_names,
            agent_id=str(agent_id) if agent_id else None,
            from_date=from_date,
            to_date=to_date,
        )
    except Exception as exc:
        logger.exception("Node export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc

    return _build_streaming_response(content, media_type, "node-analytics", fmt)


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


@router.get(
    "/metrics",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get aggregated conversation KPI metrics",
)
async def get_metrics(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    agent_id: UUID | None = None,
    compare: bool = Query(default=False),
    service: AudioService = Injected(AudioService),
):
    try:
        if compare:
            return await service.fetch_metrics_with_comparison(
                from_date=from_date, to_date=to_date, agent_id=agent_id
            )
        return await service.fetch_and_calculate_metrics(
            from_date=from_date, to_date=to_date, agent_id=agent_id
        )
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return {"error": "Error fetching metrics"}


@router.get(
    "/metrics/daily",
    dependencies=[
        Depends(auth),
        Depends(permissions(P.Dashboard.READ)),
    ],
    summary="Get daily KPI metric averages",
)
async def get_metrics_daily(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    agent_id: UUID | None = None,
    service: AudioService = Injected(AudioService),
):
    try:
        items = await service.fetch_metrics_per_day(
            from_date=from_date, to_date=to_date, agent_id=agent_id
        )
        return {"items": items}
    except Exception as e:
        logger.error(f"Error fetching daily metrics: {e}")
        return {"items": []}


def _build_streaming_response(content: bytes, media_type: str, filename_base: str, fmt: str) -> StreamingResponse:
    filename = f"{filename_base}.{EXTENSIONS[fmt]}"
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _fetch_agent_data(
    service: AnalyticsReadService,
    agent_id: UUID | None,
    from_date: date | None,
    to_date: date | None,
) -> tuple[AgentStatsSummaryResponse, AgentDailyStatsListResponse]:
    # Sequential — same SQLAlchemy session cannot handle concurrent operations
    summary = await service.get_agent_stats_summary(agent_id=agent_id, from_date=from_date, to_date=to_date)
    daily = await service.get_agent_daily_stats(agent_id=agent_id, from_date=from_date, to_date=to_date)
    return summary, daily
