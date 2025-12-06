from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from app.schemas.workflow import Workflow


class PipelineRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactType(str, Enum):
    MODEL_FILE = "model_file"
    METRICS = "metrics"
    LOGS = "logs"
    DATA = "data"
    OTHER = "other"


# Pipeline Config Schemas
class MLModelPipelineConfigBase(BaseModel):
    workflow_id: UUID = Field(..., description="Reference to the training workflow")
    is_default: bool = Field(
        default=False,
        description="Whether this is the default configuration for the model",
    )
    cron_schedule: Optional[str] = Field(
        None, max_length=100, description="Cron expression for scheduled execution"
    )


class MLModelPipelineConfigCreate(MLModelPipelineConfigBase):
    model_id: UUID = Field(..., description="Reference to the ML model")


class MLModelPipelineConfigUpdate(BaseModel):
    workflow_id: Optional[UUID] = Field(
        None, description="Reference to the training workflow"
    )
    is_default: Optional[bool] = Field(
        None, description="Whether this is the default configuration for the model"
    )
    cron_schedule: Optional[str] = Field(
        None,
        max_length=100,
        description="Cron expression for scheduled execution (null to remove)",
    )

    @field_validator("cron_schedule")
    @classmethod
    def validate_cron_schedule(cls, v):
        if v is not None and v.strip() == "":
            return None  # Convert empty string to None
        return v


class MLModelPipelineConfigRead(MLModelPipelineConfigBase):
    id: UUID
    model_id: UUID
    workflow: Optional[Workflow] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# Pipeline Run Schemas
class MLModelPipelineRunBase(BaseModel):
    model_id: UUID = Field(..., description="Reference to the ML model")
    pipeline_config_id: UUID = Field(
        ..., description="Reference to the pipeline configuration used"
    )
    workflow_id: UUID = Field(..., description="Reference to the workflow executed")


class MLModelPipelineRunCreate(MLModelPipelineRunBase):
    pass


class MLModelPipelineRunRead(MLModelPipelineRunBase):
    id: UUID
    status: PipelineRunStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    execution_output: Optional[Dict[str, Any]] = None
    execution_id: Optional[UUID] = None
    workflow: Optional[Workflow] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class MLModelPipelineRunPromote(BaseModel):
    update_model_file: bool = Field(
        default=True, description="Whether to update model.pkl_file"
    )
    update_metrics: bool = Field(
        default=True, description="Whether to update model metadata with metrics"
    )


# Pipeline Artifact Schemas
class MLModelPipelineArtifactBase(BaseModel):
    artifact_type: ArtifactType = Field(..., description="Type of artifact")
    artifact_path: str = Field(
        ..., max_length=1000, description="File path or storage location"
    )
    artifact_name: str = Field(
        ..., max_length=500, description="Display name for the artifact"
    )
    file_size: Optional[int] = Field(None, description="File size in bytes")


class MLModelPipelineArtifactCreate(MLModelPipelineArtifactBase):
    pipeline_run_id: UUID = Field(..., description="Reference to the pipeline run")


class MLModelPipelineArtifactRead(MLModelPipelineArtifactBase):
    id: UUID
    pipeline_run_id: UUID
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# Response schemas
class PipelineRunPromoteResponse(BaseModel):
    message: str
    model_updated: bool
    default_config_id: UUID
