from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict

# Breakdown dimensions the read APIs group by.
BREAKDOWN_DIMENSIONS = ("provider", "model", "agent")


class LlmUsageQueryParams:
    """Shared query params for every LLM usage read endpoint"""

    def __init__(
        self,
        from_date: Optional[date] = Query(default=None),
        to_date: Optional[date] = Query(default=None),
        agent_id: Optional[UUID] = Query(default=None),
        group_id: Optional[UUID] = Query(default=None),
        provider: Optional[str] = Query(default=None),
        model: Optional[str] = Query(default=None),
    ):
        self.from_date = from_date
        self.to_date = to_date
        self.agent_id = agent_id
        self.group_id = group_id
        self.provider = provider
        self.model = model


class LlmUsageSummaryResponse(BaseModel):
    """LLM cost and token totals for a filter. ``total_cost_usd`` sums only priced
    rows; ``cost_is_partial`` is true when some rows had no price and were left out"""

    model_config = ConfigDict(from_attributes=True)

    from_date: Optional[date] = None
    to_date: Optional[date] = None
    total_cost_usd: float
    cost_is_partial: bool
    cost_per_conversation_usd: float
    non_conversation_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_calls: int
    unpriced_calls: int
    priced_token_coverage_pct: float
    cost_source: str


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
    cost_source: str


class LlmUsageBreakdownItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    cost_usd: float
    cost_is_partial: bool
    total_tokens: int
    calls: int
    unpriced_calls: int


class LlmUsageBreakdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: str
    items: list[LlmUsageBreakdownItem]
    total: int
    cost_source: str


class LlmUsageAgentOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class LlmUsageFilterOptionsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    providers: list[str]
    models: list[str]
    agents: list[LlmUsageAgentOption]
