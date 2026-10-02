from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.db.base import Base


class WorkflowTriggerRunModel(Base):
    """A single workflow run started by an inbound webhook delivery.

    Mirrors ``workflow_schedule_runs``: the row is created PENDING at ingress,
    moved to RUNNING by the worker, and finished COMPLETED/FAILED with the
    (PII-redacted) engine output. ``input_data`` is the exact engine input built
    from the delivery, so the worker never re-parses the request.
    """

    __tablename__ = "workflow_trigger_runs"
    __table_args__ = (
        Index("idx_workflow_trigger_runs_webhook_id", "webhook_id"),
        Index("idx_workflow_trigger_runs_status", "status"),
        Index("idx_workflow_trigger_runs_created_at", "created_at"),
    )

    webhook_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # The workflow version actually executed (resolved from the agent at run time).
    workflow_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
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
    # Caller-supplied delivery id; unique per webhook (partial index) so a retry
    # of the same delivery returns the first run instead of starting another.
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    execution_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    webhook = relationship("WebhookModel", uselist=False)
