from typing import Optional

from sqlalchemy import Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FallbackChainModel(Base):
    """A reusable, named ordered list of LLM providers tried in priority order.

    `provider_ids` is an ordered list of `llm_providers.id` strings (index 0 =
    highest priority). `retry_policy` holds `{ "retry_count": int,
    "backoff_seconds": float }`. No secrets are stored here — only references to
    existing LLM providers.
    """

    __tablename__ = "fallback_chains"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="fallback_chains_pk"),
    )

    name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    retry_policy: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
