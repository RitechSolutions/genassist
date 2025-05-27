from sqlalchemy import UUID, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base import Base

class UserRoleModel(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)

    # Optional relationships (if needed)
    user = relationship("UserModel", back_populates="user_roles", foreign_keys=[user_id])
    role = relationship("RoleModel", back_populates="user_roles", foreign_keys=[role_id])
