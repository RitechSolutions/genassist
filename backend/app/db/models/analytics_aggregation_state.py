from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalyticsAggregationStateModel(Base):
    """Per-tenant single-row cursor for the aggregation job (state_key is always 1)."""

    __tablename__ = "analytics_aggregation_state"
    __table_args__ = (
        # Adopts mixin's primary_key to keep create_all() and migrations aligned on
        # constraint name.
        PrimaryKeyConstraint(name="analytics_aggregation_state_pk"),
        UniqueConstraint("state_key", name="uq_analytics_aggregation_state_key"),
        CheckConstraint("state_key = 1", name="ck_analytics_aggregation_state_key"),
    )

    state_key: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_incremental_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
