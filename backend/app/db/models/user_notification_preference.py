from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNotificationPreferenceModel(Base):
    __tablename__ = "user_notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "notification_type_id",
            name="uq_user_notification_preferences_user_type",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notification_type_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
