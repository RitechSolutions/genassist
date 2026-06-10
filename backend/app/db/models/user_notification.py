from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNotificationModel(Base):
    __tablename__ = "user_notifications"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "user_id",
            name="uq_user_notifications_notification_user",
        ),
        Index("ix_user_notifications_user_created", "user_id", "created_at"),
        Index("ix_user_notifications_user_read", "user_id", "is_read", "created_at"),
    )

    notification_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
