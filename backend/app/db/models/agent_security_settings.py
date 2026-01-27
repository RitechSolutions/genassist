from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentSecuritySettingsModel(Base):
    __tablename__ = "agent_security_settings"

    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Token-based auth settings
    token_based_auth: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    token_expiration_minutes: Mapped[Integer] = mapped_column(Integer, nullable=True)

    # CORS settings
    cors_allowed_origins: Mapped[str] = mapped_column(Text, nullable=True)

    # Rate limiting settings
    rate_limit_conversation_start_per_minute: Mapped[Integer] = mapped_column(Integer, nullable=True)
    rate_limit_conversation_start_per_hour: Mapped[Integer] = mapped_column(Integer, nullable=True)
    rate_limit_conversation_update_per_minute: Mapped[Integer] = mapped_column(Integer, nullable=True)
    rate_limit_conversation_update_per_hour: Mapped[Integer] = mapped_column(Integer, nullable=True)

    # reCAPTCHA settings
    recaptcha_enabled: Mapped[bool] = mapped_column(Boolean, nullable=True)
    recaptcha_project_id: Mapped[str] = mapped_column(String(200), nullable=True)
    recaptcha_site_key: Mapped[str] = mapped_column(String(200), nullable=True)
    recaptcha_min_score: Mapped[str] = mapped_column(String(10), nullable=True)
    gcp_svc_account: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationship
    agent = relationship("AgentModel", back_populates="security_settings", uselist=False)
