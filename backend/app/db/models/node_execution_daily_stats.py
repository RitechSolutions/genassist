from datetime import date
from uuid import UUID

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NodeExecutionDailyStatsModel(Base):
    """
    Pre-aggregated daily execution statistics per agent per node type.

    Populated by the analytics_aggregation Celery task running twice daily.
    Enables breakdown of workflow node performance without scanning raw logs.
    """

    __tablename__ = "node_execution_daily_stats"

    __table_args__ = (
        UniqueConstraint(
            "agent_id", "node_type", "stat_date",
            name="uq_node_execution_daily_stats_agent_node_date"
        ),
    )

    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    node_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    stat_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    execution_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    avg_execution_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    min_execution_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    max_execution_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    total_execution_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
