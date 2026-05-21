from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNotificationReadModel(Base):
    """Per-user read receipt for a single notification instance (synthetic feed id)."""

    __tablename__ = "user_notification_reads"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "notification_id",
            name="uq_user_notification_reads_user_notification",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
