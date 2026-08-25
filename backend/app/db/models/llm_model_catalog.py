from sqlalchemy import Index, Integer, PrimaryKeyConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LlmModelCatalogModel(Base):
    """Tenant-registered LLM models, keyed like ``llm_cost_rates``.

    This table is an *overlay*: it only ever holds models a tenant added on top of
    the built-in lists in ``LLM_FORM_SCHEMAS``. The hardcoded lists stay the source
    of truth for everything shipped with the product and win on a key collision, so
    an empty table reproduces the previous behaviour exactly.
    """

    __tablename__ = "llm_model_catalog"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="llm_model_catalog_pk"),
        Index("ix_llm_model_catalog_provider_key", "provider_key"),
        Index(
            "uq_llm_model_catalog_provider_model_active",
            "provider_key",
            "model_key",
            unique=True,
            postgresql_where=text("is_deleted = 0"),
        ),
    )

    # Matches the LLM_FORM_SCHEMAS key ("openai", "groq", ...) and llm_cost_rates.provider_key
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # The value sent to the provider API, e.g. "llama-3.3-70b-versatile"
    model_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # What the Model dropdown shows
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
