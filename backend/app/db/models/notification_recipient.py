from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationRecipientModel(Base):
    __tablename__ = "notification_recipients"
    __table_args__ = (
        UniqueConstraint(
            "notification_type_id",
            "principal_type",
            "principal_id",
            name="uq_notification_recipients_type_principal",
        ),
        CheckConstraint(
            "principal_type IN ('user', 'group')",
            name="ck_notification_recipients_principal_type",
        ),
    )

    notification_type_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("notification_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    principal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    principal_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
