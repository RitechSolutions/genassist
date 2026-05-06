from sqlalchemy import Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from app.db.base import Base


class TenantNotificationPreferenceModel(Base):
    __tablename__ = "tenant_notification_preferences"

    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    workflow_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
