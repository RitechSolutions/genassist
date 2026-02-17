from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class DashboardSummaryStats(BaseModel):
    """Summary statistics for the dashboard header."""
    active_agents: int
    workflow_runs: int
    avg_response_time_ms: int

    model_config = ConfigDict(from_attributes=True)


class ActiveConversationItem(BaseModel):
    """Single active conversation item for the dashboard."""
    id: UUID
    topic: Optional[str] = None
    feedback: Optional[str] = None  # Good, Bad, Neutral
    duration: int = 0
    last_message: Optional[str] = None
    status: str
    created_at: datetime
    negative_reason: Optional[str] = None
    in_progress_hostility_score: int = 0

    model_config = ConfigDict(from_attributes=True)


class ActiveConversationsResponse(BaseModel):
    """Active conversations section response with pagination."""
    total: int
    good_count: int
    neutral_count: int
    bad_count: int
    conversations: list[ActiveConversationItem]
    page: int = 1
    page_size: int = 10
    has_more: bool = False

    model_config = ConfigDict(from_attributes=True)


class AgentStatsItem(BaseModel):
    """Single agent with its statistics."""
    id: UUID
    name: str
    conversations_today: int = 0
    resolution_rate: Decimal = Decimal("0.00")
    avg_response_time_ms: int = 0
    cost: Decimal = Decimal("0.00")
    is_active: bool = False

    model_config = ConfigDict(from_attributes=True)


class AgentStatsResponse(BaseModel):
    """Your Agents section response."""
    agents: list[AgentStatsItem]

    model_config = ConfigDict(from_attributes=True)


class IntegrationItem(BaseModel):
    """Single integration item."""
    id: UUID
    name: str
    type: str
    description: Optional[str] = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class IntegrationsResponse(BaseModel):
    """Integrations section response."""
    integrations: list[IntegrationItem]

    model_config = ConfigDict(from_attributes=True)


class DashboardResponse(BaseModel):
    """Full dashboard response combining all sections."""
    summary: DashboardSummaryStats
    active_conversations: ActiveConversationsResponse
    agents: AgentStatsResponse
    integrations: IntegrationsResponse

    model_config = ConfigDict(from_attributes=True)
