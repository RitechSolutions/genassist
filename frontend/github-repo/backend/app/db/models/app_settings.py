from typing import Any
from sqlalchemy import String, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AppSettingsModel(Base):
    __tablename__ = "app_settings"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint(
            "type IN ('Zendesk', 'WhatsApp', 'Gmail', 'Microsoft', 'Slack', 'Jira', 'Other')",
            name='app_settings_type_check'
        ),
    )
