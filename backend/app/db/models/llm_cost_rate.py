from decimal import Decimal
from typing import Optional

from sqlalchemy import Index, Numeric, PrimaryKeyConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LlmCostRateModel(Base):
    """Per-tenant LLM token pricing (USD per 1K tokens)."""

    __tablename__ = "llm_cost_rates"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="llm_cost_rates_pk"),
        Index("ix_llm_cost_rates_provider_model", "provider_key", "model_key"),
        Index(
            "uq_llm_cost_rates_provider_model_active",
            "provider_key",
            "model_key",
            unique=True,
            postgresql_where=text("is_deleted = 0"),
        ),
    )

    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_key: Mapped[str] = mapped_column(String(512), nullable=False)
    input_per_1k: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    output_per_1k: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    cache_read_per_1k: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)
    cache_creation_per_1k: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 10), nullable=True)
