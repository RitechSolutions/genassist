from app.db.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String


class UserTypeModel(Base):
    __tablename__ = "user_types"

    name: Mapped[str] = mapped_column(String(255), unique=True)

    users = relationship("UserModel", back_populates="user_type", foreign_keys="[UserModel.user_type_id]")
    