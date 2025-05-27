# from uuid import UUID
# from sqlalchemy import ForeignKey, PrimaryKeyConstraint, UniqueConstraint
# from sqlalchemy.orm import Mapped, mapped_column, relationship
# from app.db.base import Base


# class ApiKeyPermissionModel(Base):
#     __tablename__ = "api_key_permissions"
#     __table_args__ = (
#         PrimaryKeyConstraint("id", name="api_key_permissions_pk"),
#         UniqueConstraint("api_key_id", "permission_id", name="uq_api_key_permissions_pair")
#     )

#     api_key_id: Mapped[UUID] = mapped_column(ForeignKey("api_keys.id"), nullable=False)
#     permission_id: Mapped[UUID] = mapped_column(ForeignKey("permissions.id"), nullable=False)

#     api_key = relationship("ApiKeyModel", back_populates="api_key_permissions")
#     permission = relationship("PermissionModel", back_populates="api_key_permissions")
