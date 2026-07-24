import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P
from app.core.utils.cache_headers import no_store_headers
from app.schemas.llm_usage import (
    BREAKDOWN_DIMENSIONS,
    LlmUsageBreakdownResponse,
    LlmUsageFilterOptionsResponse,
    LlmUsageQueryParams,
    LlmUsageSummaryResponse,
    LlmUsageTimeseriesResponse,
)
from app.schemas.llm_usage_control import LlmUsageControlRead, LlmUsageCutoverRequest
from app.services.llm_usage_control import LlmUsageControlService
from app.services.llm_usage_export import EXTENSIONS, VALID_FORMATS, export_llm_usage
from app.services.llm_usage_read import LlmUsageReadService

router = APIRouter()


def _validate_dimension(dimension: str) -> str:
    if dimension not in BREAKDOWN_DIMENSIONS:
        raise HTTPException(status_code=400, detail=f"dimension must be one of: {', '.join(BREAKDOWN_DIMENSIONS)}")
    return dimension


@router.get(
    "/control",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.Dashboard.READ))],
    summary="Get LLM usage capture / shadow / cutover state",
)
async def get_control(
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    return await service.get_control()


@router.post(
    "/capture",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.WRITE))],
    summary="Activate LLM usage capture",
)
async def activate_capture(
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    """Enable usage capture and mark the backfill start time. No request body"""
    return await service.activate_capture()


@router.post(
    "/shadow/start",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.WRITE))],
    summary="Start shadow reconciliation",
)
async def start_shadow(
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    return await service.start_shadow()


@router.post(
    "/cutover",
    response_model=LlmUsageControlRead,
    dependencies=[Depends(auth), Depends(permissions(P.AppSettings.WRITE))],
    summary="Flip the dashboard cost source to the ledger (reversible)",
)
async def set_cutover(
    body: LlmUsageCutoverRequest,
    service: LlmUsageControlService = Injected(LlmUsageControlService),
) -> LlmUsageControlRead:
    return await service.set_cutover(body.enabled)


@router.get(
    "/summary",
    response_model=LlmUsageSummaryResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Dashboard.READ))],
    summary="Canonical LLM cost / token / coverage totals",
)
async def get_summary(
    params: LlmUsageQueryParams = Depends(),
    service: LlmUsageReadService = Injected(LlmUsageReadService),
) -> LlmUsageSummaryResponse:
    return await service.get_summary(params)


@router.get(
    "/timeseries",
    response_model=LlmUsageTimeseriesResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Dashboard.READ))],
    summary="Daily LLM cost / tokens / calls",
)
async def get_timeseries(
    params: LlmUsageQueryParams = Depends(),
    service: LlmUsageReadService = Injected(LlmUsageReadService),
) -> LlmUsageTimeseriesResponse:
    return await service.get_timeseries(params)


@router.get(
    "/breakdown",
    response_model=LlmUsageBreakdownResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Dashboard.READ))],
    summary="LLM cost / tokens grouped by provider, model, or agent",
)
async def get_breakdown(
    params: LlmUsageQueryParams = Depends(),
    dimension: str = Query(default="provider"),
    service: LlmUsageReadService = Injected(LlmUsageReadService),
) -> LlmUsageBreakdownResponse:
    return await service.get_breakdown(params, _validate_dimension(dimension))


@router.get(
    "/filter-options",
    response_model=LlmUsageFilterOptionsResponse,
    dependencies=[Depends(auth), Depends(permissions(P.Dashboard.READ))],
    summary="Distinct providers, models, and agents available for filtering",
)
async def get_filter_options(
    params: LlmUsageQueryParams = Depends(),
    service: LlmUsageReadService = Injected(LlmUsageReadService),
) -> LlmUsageFilterOptionsResponse:
    return await service.get_filter_options(params)


@router.get(
    "/export",
    dependencies=[Depends(auth), Depends(permissions(P.Dashboard.READ))],
    summary="Export LLM usage report (csv / xlsx / pdf)",
)
async def export_usage(
    params: LlmUsageQueryParams = Depends(),
    dimension: str = Query(default="provider"),
    fmt: str = Query(default="csv", alias="format"),
    service: LlmUsageReadService = Injected(LlmUsageReadService),
) -> StreamingResponse:
    if fmt not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of: {', '.join(sorted(VALID_FORMATS))}")
    dimension = _validate_dimension(dimension)
    summary = await service.get_summary(params)
    breakdown = await service.get_breakdown(params, dimension)
    content, media_type = export_llm_usage(fmt, summary, breakdown, params.from_date, params.to_date)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="llm-usage.{EXTENSIONS[fmt]}"',
            **no_store_headers(),
        },
    )
