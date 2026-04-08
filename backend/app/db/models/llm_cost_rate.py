from sqlalchemy import Index, Numeric, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LlmCostRateModel(Base):
    """Per-tenant LLM token pricing (USD per 1K tokens)."""

    __tablename__ = "llm_cost_rates"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="llm_cost_rates_pk"),
        Index("ix_llm_cost_rates_provider_model", "provider_key", "model_key"),
    )

    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_key: Mapped[str] = mapped_column(String(512), nullable=False)
    input_per_1k: Mapped[float] = mapped_column(Numeric(18, 10), nullable=False)
    output_per_1k: Mapped[float] = mapped_column(Numeric(18, 10), nullable=False)
