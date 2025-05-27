from sqlalchemy import PrimaryKeyConstraint, UniqueConstraint, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class RolePermissionModel(Base):
    __tablename__ = 'role_permissions'
    __table_args__ = (
        PrimaryKeyConstraint("id", name="role_permissions_pk"),
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission_pair")
    )

    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    permission_id: Mapped[UUID] = mapped_column(ForeignKey("permissions.id"), nullable=False)

    role = relationship("RoleModel", back_populates="role_permissions")
    permission = relationship("PermissionModel", back_populates="role_permissions")

    def __repr__(self):
        return (f"<RolePermission("
                f"id={self.id}, role_id={self.role_id}, permission_id={self.permission_id})>")
