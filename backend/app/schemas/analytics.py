from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ── Agent daily stats ──────────────────────────────────────────────────────────

class AgentDailyStatsItem(BaseModel):
    id: UUID
    agent_id: UUID
    stat_date: date
    execution_count: int
    success_count: int
    error_count: int
    avg_response_ms: Optional[float] = None
    min_response_ms: Optional[float] = None
    max_response_ms: Optional[float] = None
    total_nodes_executed: int
    avg_success_rate: Optional[float] = None
    rag_used_count: int
    unique_conversations: int
    finalized_conversations: int = 0
    in_progress_conversations: int = 0
    thumbs_up_count: int = 0
    thumbs_down_count: int = 0
    last_aggregated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentDailyStatsListResponse(BaseModel):
    items: list[AgentDailyStatsItem]
    total: int

    model_config = ConfigDict(from_attributes=True)


# ── Agent summary (aggregated across date range) ───────────────────────────────

class AgentStatsSummaryResponse(BaseModel):
    agent_id: Optional[UUID] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    total_executions: int
    total_success: int
    total_errors: int
    avg_response_ms: Optional[float] = None
    avg_success_rate: Optional[float] = None
    total_rag_used: int
    total_unique_conversations: int
    total_finalized_conversations: int = 0
    total_in_progress_conversations: int = 0
    total_thumbs_up: int = 0
    total_thumbs_down: int = 0

    model_config = ConfigDict(from_attributes=True)


# ── Node daily stats ───────────────────────────────────────────────────────────

class NodeDailyStatsItem(BaseModel):
    id: UUID
    agent_id: UUID
    node_type: str
    stat_date: date
    execution_count: int
    success_count: int
    failure_count: int
    avg_execution_ms: Optional[float] = None
    min_execution_ms: Optional[float] = None
    max_execution_ms: Optional[float] = None
    total_execution_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class NodeDailyStatsListResponse(BaseModel):
    items: list[NodeDailyStatsItem]
    total: int

    model_config = ConfigDict(from_attributes=True)


# ── Node type breakdown (per agent) ───────────────────────────────────────────

class NodeTypeBreakdownItem(BaseModel):
    node_type: str
    execution_count: int
    success_count: int
    failure_count: int
    success_rate: Optional[float] = None
    avg_execution_ms: Optional[float] = None
    total_execution_ms: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class NodeTypeBreakdownResponse(BaseModel):
    agent_id: UUID
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    items: list[NodeTypeBreakdownItem]

    model_config = ConfigDict(from_attributes=True)
