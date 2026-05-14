from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationTypeRecipientGroupModel(Base):
    """Admin-selected groups (members + supervisors of those groups) for a notification type."""

    __tablename__ = "notification_type_recipient_groups"
    __table_args__ = (
        UniqueConstraint(
            "notification_type_id",
            "group_id",
            name="uq_nt_recipient_groups_type_group",
        ),
    )

    notification_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notification_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("user_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
