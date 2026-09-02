from datetime import date, datetime
from typing import Annotated, Literal, Optional, get_args
from uuid import UUID

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict

BreakdownDimension = Literal["provider", "model", "agent", "source", "llm", "evaluation_method", "node"]
BREAKDOWN_DIMENSIONS: tuple[str, ...] = get_args(BreakdownDimension)
ExportDimension = Literal["provider", "model", "agent", "source"]
EXPORT_DIMENSIONS: tuple[str, ...] = get_args(ExportDimension)

ExportFormat = Literal["csv", "xlsx", "pdf"]


class LlmUsageQueryParams:
    """Shared query params for every LLM usage read endpoint"""

    def __init__(
        self,
        from_date: Annotated[Optional[date], Query()] = None,
        to_date: Annotated[Optional[date], Query()] = None,
        agent_id: Annotated[Optional[UUID], Query()] = None,
        group_id: Annotated[Optional[UUID], Query()] = None,
        provider: Annotated[Optional[str], Query()] = None,
        model: Annotated[Optional[str], Query()] = None,
    ):
        if from_date is not None and to_date is not None and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date must be on or before to_date")
        self.from_date = from_date
        self.to_date = to_date
        self.agent_id = agent_id
        self.group_id = group_id
        self.provider = provider
        self.model = model


class LlmUsageSummaryResponse(BaseModel):
    """LLM cost and token totals for a filter. ``total_cost_usd`` sums only priced
    rows; ``cost_is_partial`` is true when some rows had no price and were left out.

    ``agent_studio_test_cost_usd`` covers Agent Studio workflow and node tests only.

    ``last_unpriced_at`` is when an unpriced call was last *recorded* tenant-wide,
    ignoring the filters, so a client can tell whether one has landed since it last
    reported the gap. It is only populated when the filtered window has unpriced calls.

    Prompt tokens sent, normalized across providers. Includes cache (already
    in total_input_tokens). If provider reports input minus cache, we add it back
    so input + output = total_tokens."""

    model_config = ConfigDict(from_attributes=True)

    from_date: Optional[date] = None
    to_date: Optional[date] = None
    total_cost_usd: float
    cost_is_partial: bool
    cost_per_conversation_usd: Optional[float] = None
    agent_studio_test_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_calls: int
    configured_calls: int
    fallback_calls: int
    legacy_estimate_calls: int
    unpriced_calls: int
    priced_token_coverage_pct: float
    last_unpriced_at: Optional[datetime] = None


class LlmUsageTimeseriesItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stat_date: date
    cost_usd: float
    total_tokens: int
    calls: int
    unpriced_calls: int


class LlmUsageTimeseriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[LlmUsageTimeseriesItem]
    total: int


class LlmUsageBreakdownItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    cost_usd: float
    cost_is_partial: bool
    total_tokens: int
    calls: int
    unpriced_calls: int
    removed: Optional[bool] = None


class LlmUsageBreakdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: BreakdownDimension
    items: list[LlmUsageBreakdownItem]
    total: int


class LlmUsageAgentOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class LlmUsageFilterOptionsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    providers: list[str]
    models: list[str]
    agents: list[LlmUsageAgentOption]
