from typing import Optional

from sqlalchemy import (
    String,
    Text,
    Index,
    ForeignKey,
    Boolean,
    Enum as SQLEnum,
    DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.utils.enums.workflow_schedule_enum import (
    WorkflowScheduleRunStatus,
    ThreadIdMode,
)


class WorkflowScheduleModel(Base):
    """A recurring schedule that executes an agent's latest workflow version."""

    __tablename__ = "workflow_schedules"
    __table_args__ = (
        Index("idx_workflow_schedules_agent_id", "agent_id"),
        Index("idx_workflow_schedules_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The schedule targets an agent; at run time we resolve the agent's current
    # workflow_id so the latest published version is always executed.
    agent_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    cron_schedule: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # message + any input-node fields passed to the workflow engine.
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    thread_id_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=ThreadIdMode.PER_RUN.value
    )
    fixed_thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_run_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    agent = relationship("AgentModel", lazy="selectin")
    runs = relationship(
        "WorkflowScheduleRunModel",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )


class WorkflowScheduleRunModel(Base):
    """A single execution of a workflow schedule, with status and output."""

    __tablename__ = "workflow_schedule_runs"
    __table_args__ = (
        Index("idx_workflow_schedule_runs_schedule_id", "schedule_id"),
        Index("idx_workflow_schedule_runs_status", "status"),
        Index("idx_workflow_schedule_runs_created_at", "created_at"),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # The workflow version actually executed (resolved from the agent at run time).
    workflow_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[WorkflowScheduleRunStatus] = mapped_column(
        SQLEnum(
            WorkflowScheduleRunStatus,
            name="workflow_schedule_run_status_enum",
            create_constraint=True,
        ),
        nullable=False,
        default=WorkflowScheduleRunStatus.PENDING,
    )
    started_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    execution_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Relationships
    schedule = relationship("WorkflowScheduleModel", back_populates="runs")