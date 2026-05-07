from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationTypeModel(Base):
    __tablename__ = "notification_types"

    type: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_tenant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
