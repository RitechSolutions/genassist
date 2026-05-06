from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNotificationPreferenceModel(Base):
    __tablename__ = "user_notification_preferences"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    conversation_started: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conversation_hostility: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conversation_finalized_hostility: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
