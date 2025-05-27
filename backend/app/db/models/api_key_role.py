from sqlalchemy import UUID, ForeignKey, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ApiKeyRoleModel(Base):
    __tablename__ = "api_key_roles"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="api_key_roles_pk"),
        UniqueConstraint("api_key_id", "role_id", name="uq_api_key_roles_pair")
    )
    api_key_id: Mapped[UUID] = mapped_column(ForeignKey("api_keys.id",), nullable=False)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)

    api_key = relationship("ApiKeyModel", back_populates="api_key_roles", foreign_keys=[api_key_id])
    role = relationship("RoleModel", back_populates="api_key_roles", foreign_keys=[role_id])

