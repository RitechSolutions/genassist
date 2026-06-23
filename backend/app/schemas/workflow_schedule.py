from uuid import UUID
from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.core.utils.enums.workflow_schedule_enum import (
    WorkflowScheduleRunStatus,
    ThreadIdMode,
)


class WorkflowScheduleBase(BaseModel):
    name: str = Field(..., max_length=255, description="Display name for the schedule")
    agent_id: UUID = Field(..., description="Agent whose latest workflow will run")
    cron_schedule: str = Field(
        ..., max_length=100, description="Cron expression (minute hour day month weekday)"
    )
    is_active: bool = Field(default=True, description="Whether the schedule is enabled")
    input_data: Optional[Dict[str, Any]] = Field(
        default=None, description="message and any input-node fields passed to the workflow"
    )
    thread_id_mode: ThreadIdMode = Field(
        default=ThreadIdMode.PER_RUN,
        description="per_run = fresh thread each run; fixed = reuse fixed_thread_id",
    )
    fixed_thread_id: Optional[str] = Field(
        default=None, max_length=255, description="Thread id reused when thread_id_mode is fixed"
    )


class WorkflowScheduleCreate(WorkflowScheduleBase):
    pass


class WorkflowScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    agent_id: Optional[UUID] = None
    cron_schedule: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    input_data: Optional[Dict[str, Any]] = None
    thread_id_mode: Optional[ThreadIdMode] = None
    fixed_thread_id: Optional[str] = Field(None, max_length=255)

    @field_validator("cron_schedule")
    @classmethod
    def validate_cron_schedule(cls, v):
        if v is not None and v.strip() == "":
            return None
        return v


class WorkflowScheduleRead(WorkflowScheduleBase):
    id: UUID
    last_run_at: Optional[datetime] = None
    # Latest run summary for list display
    last_run_status: Optional[WorkflowScheduleRunStatus] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowScheduleRunRead(BaseModel):
    id: UUID
    schedule_id: UUID
    agent_id: UUID
    workflow_id: Optional[UUID] = None
    thread_id: Optional[str] = None
    status: WorkflowScheduleRunStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_output: Optional[Dict[str, Any]] = None
    execution_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)