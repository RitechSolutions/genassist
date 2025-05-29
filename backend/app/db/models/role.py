from typing import Optional
from sqlalchemy import Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class RoleModel(Base):
    __tablename__ = 'roles'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='roles_pk'),
        UniqueConstraint('name', name='roles_unique')
    )

    name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    role_type: Mapped[Optional[str]] = mapped_column(String(50), server_default='external')
    is_active: Mapped[Optional[int]] = mapped_column(Integer)

    # In Roles model
    user_roles = relationship("UserRoleModel", back_populates="role")
    api_key_roles = relationship("ApiKeyRoleModel", back_populates="role", foreign_keys="[ApiKeyRoleModel.role_id]")

<<<<<<< HEAD
    role_permissions = relationship("RolePermissionModel", back_populates="role")
=======
    role_permissions = relationship("RolePermissionModel", back_populates="role", cascade="all, delete-orphan")
>>>>>>> development

    @property
    def permissions(self) -> list[str]:
        """
        Returns a list of permission names (strings) granted to this role.
        """
        return [
            rp.permission.name
            for rp in self.role_permissions
            if rp.permission and rp.permission.is_active
        ]

    @property
    def api_keys(self):
        return [akr.api_key for akr in self.api_key_roles if akr.api_key]
