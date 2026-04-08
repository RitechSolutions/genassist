from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserGroupModel(Base):
    __tablename__ = "user_groups"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parent_group_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("user_groups.id"), nullable=True
    )

    members = relationship(
        "UserModel",
        back_populates="group",
        foreign_keys="[UserModel.group_id]",
    )
    parent = relationship(
        "UserGroupModel",
        remote_side="UserGroupModel.id",
        foreign_keys=[parent_group_id],
    )

    def __repr__(self):
        return f"<UserGroup(id={self.id}, name={self.name})>"