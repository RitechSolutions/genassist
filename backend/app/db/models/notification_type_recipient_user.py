from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationTypeRecipientUserModel(Base):
    """Admin-selected users who receive a notification type when tenant-wide is off."""

    __tablename__ = "notification_type_recipient_users"
    __table_args__ = (
        UniqueConstraint(
            "notification_type_id",
            "user_id",
            name="uq_nt_recipient_users_type_user",
        ),
    )

    notification_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notification_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
