from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserGroupModel(Base):
    __tablename__ = "user_groups"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    members = relationship(
        "UserModel",
        back_populates="group",
        foreign_keys="[UserModel.group_id]",
    )
    supervisors = relationship(
        "UserSupervisedGroupModel",
        back_populates="group",
        foreign_keys="[UserSupervisedGroupModel.group_id]",
    )

    def __repr__(self):
        return f"<UserGroup(id={self.id}, name={self.name})>"