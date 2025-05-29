from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class PermissionModel(Base):
    __tablename__ = 'permissions'

    name: Mapped[str] = mapped_column(String(255), unique=True)   # e.g., "Post:user_types"
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(255)) 

    # Many-to-many via role_permissions
<<<<<<< HEAD
    role_permissions = relationship("RolePermissionModel", back_populates="permission")
=======
    role_permissions = relationship("RolePermissionModel", back_populates="permission", cascade="all, delete-orphan")
>>>>>>> development
    # api_key_permissions = relationship("ApiKeyPermissionModel", back_populates="permission")

    def __repr__(self):
        return f"<Permissions(id={self.id}, name={self.name})>"

