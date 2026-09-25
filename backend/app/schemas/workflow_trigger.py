from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus

TriggerMethod = Literal["POST", "GET"]
TriggerAuthMode = Literal["bearer", "hmac"]


class WorkflowTriggerProvision(BaseModel):
    """Create (or fetch) the endpoint of a Webhook Trigger node."""

    agent_id: UUID
    node_id: str = Field(..., min_length=1, max_length=255)
    # Public API base (e.g. "https://host/api/"); the backend falls back to the
    # request's own URL when omitted.
    base_url: Optional[str] = None


class WorkflowTriggerUpdate(BaseModel):
    method: Optional[TriggerMethod] = None
    auth_mode: Optional[TriggerAuthMode] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=0, le=6000, description="0 disables the limit")
    is_active: Optional[bool] = None


class WorkflowTriggerRead(BaseModel):
    id: UUID
    agent_id: UUID
    node_id: str
    url: str
    method: TriggerMethod
    auth_mode: TriggerAuthMode
    rate_limit_per_minute: int
    is_active: bool
    last_run_status: Optional[WorkflowScheduleRunStatus] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowTriggerProvisionResponse(WorkflowTriggerRead):
    # Plaintext secret, returned only when the endpoint was just created (or
    # rotated); afterwards it can only be re-read via reveal-secret.
    secret: Optional[str] = None
    created: bool = False


class WorkflowTriggerSecret(BaseModel):
    secret: str
    auth_mode: TriggerAuthMode


class WorkflowTriggerTestRequest(BaseModel):
    # Delivery body to simulate; falls back to the node's saved sample payload.
    payload: Optional[Any] = None
    query: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


class WorkflowTriggerDeliveryResponse(BaseModel):
    """What the public endpoint (and the test endpoint) answer."""

    run_id: UUID
    status: WorkflowScheduleRunStatus
    thread_id: Optional[str] = None
    duplicate: bool = False


class WorkflowTriggerRunRead(BaseModel):
    id: UUID
    webhook_id: UUID
    agent_id: UUID
    node_id: str
    workflow_id: Optional[UUID] = None
    thread_id: Optional[str] = None
    status: WorkflowScheduleRunStatus
    idempotency_key: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_output: Optional[Dict[str, Any]] = None
    execution_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowTriggerRunSummary(BaseModel):
    """List row: no payloads, so the run list stays small."""

    id: UUID
    webhook_id: UUID
    workflow_id: Optional[UUID] = None
    thread_id: Optional[str] = None
    status: WorkflowScheduleRunStatus
    idempotency_key: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
