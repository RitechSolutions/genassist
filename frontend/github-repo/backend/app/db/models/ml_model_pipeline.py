from typing import Optional
from sqlalchemy import String, Text, Index, ForeignKey, Boolean, BigInteger, Enum as SQLEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID
import enum

from app.db.base import Base


class PipelineRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactType(str, enum.Enum):
    MODEL_FILE = "model_file"
    METRICS = "metrics"
    LOGS = "logs"
    DATA = "data"
    OTHER = "other"


class MLModelPipelineConfig(Base):
    __tablename__ = 'ml_model_pipeline_configs'
    __table_args__ = (
        Index('idx_pipeline_configs_model_id', 'model_id'),
        Index('idx_pipeline_configs_workflow_id', 'workflow_id'),
    )

    model_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('ml_models.id', ondelete='CASCADE'),
        nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('workflows.id', ondelete='CASCADE'),
        nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cron_schedule: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    model = relationship("MLModel", back_populates="pipeline_configs")
    workflow = relationship("WorkflowModel", lazy="selectin")
    pipeline_runs = relationship(
        "MLModelPipelineRun",
        back_populates="pipeline_config",
        cascade="all, delete-orphan"
    )


class MLModelPipelineRun(Base):
    __tablename__ = 'ml_model_pipeline_runs'
    __table_args__ = (
        Index('idx_pipeline_runs_model_id', 'model_id'),
        Index('idx_pipeline_runs_config_id', 'pipeline_config_id'),
        Index('idx_pipeline_runs_status', 'status'),
        Index('idx_pipeline_runs_created_at', 'created_at'),
        Index('idx_pipeline_runs_model_status', 'model_id', 'status'),
    )

    model_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('ml_models.id', ondelete='CASCADE'),
        nullable=False
    )
    pipeline_config_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('ml_model_pipeline_configs.id', ondelete='CASCADE'),
        nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('workflows.id', ondelete='CASCADE'),
        nullable=False
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        SQLEnum(PipelineRunStatus, name='pipeline_run_status_enum', create_constraint=True),
        nullable=False,
        default=PipelineRunStatus.PENDING
    )
    started_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    execution_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Relationships
    model = relationship("MLModel", back_populates="pipeline_runs")
    pipeline_config = relationship("MLModelPipelineConfig", back_populates="pipeline_runs")
    workflow = relationship("WorkflowModel", lazy="selectin")
    artifacts = relationship(
        "MLModelPipelineArtifact",
        back_populates="pipeline_run",
        cascade="all, delete-orphan"
    )


class MLModelPipelineArtifact(Base):
    __tablename__ = 'ml_model_pipeline_artifacts'
    __table_args__ = (
        Index('idx_pipeline_artifacts_run_id', 'pipeline_run_id'),
        Index('idx_pipeline_artifacts_type', 'artifact_type'),
    )

    pipeline_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('ml_model_pipeline_runs.id', ondelete='CASCADE'),
        nullable=False
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        SQLEnum(ArtifactType, name='artifact_type_enum', create_constraint=True),
        nullable=False
    )
    artifact_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    artifact_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Relationships
    pipeline_run = relationship("MLModelPipelineRun", back_populates="artifacts")

