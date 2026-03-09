from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentExecutionDailyStatsModel(Base):
    """
    Pre-aggregated daily execution statistics per agent.

    Populated by the analytics_aggregation Celery task running twice daily.
    Queries against agent_response_logs.raw_response are expensive; this table
    provides a cheap read path for analytics dashboards.
    """

    __tablename__ = "agent_execution_daily_stats"

    __table_args__ = (
        UniqueConstraint("agent_id", "stat_date", name="uq_agent_execution_daily_stats_agent_date"),
    )

    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
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

    error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    avg_response_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    min_response_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    max_response_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    total_response_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    total_nodes_executed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    avg_success_rate: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    total_success_rate_sum: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    rag_used_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    unique_conversations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    finalized_conversations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    in_progress_conversations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    thumbs_up_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    thumbs_down_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    last_aggregated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
