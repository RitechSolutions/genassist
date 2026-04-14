from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserSupervisedGroupModel(Base):
    __tablename__ = "user_supervised_groups"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    group_id: Mapped[UUID] = mapped_column(ForeignKey("user_groups.id"), nullable=False)

    user = relationship("UserModel", back_populates="supervised_group_memberships", foreign_keys=[user_id])
    group = relationship("UserGroupModel", back_populates="supervisors", foreign_keys=[group_id])