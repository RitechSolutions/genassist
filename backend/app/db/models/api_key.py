from datetime import datetime
from typing import Optional
from sqlalchemy import UUID, DateTime, Integer, PrimaryKeyConstraint, String, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class ApiKeyModel(Base):
    __tablename__ = 'api_keys'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='api_keys_pk'),
        UniqueConstraint('name', name='api_keys_unique')
        )

    name: Mapped[Optional[str]] = mapped_column(String(255))
    key_val: Mapped[Optional[str]] = mapped_column(String(255))
    hashed_value: Mapped[Optional[str]] = mapped_column(String(255))
    previous_hashed_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    previous_hashed_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    credential_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Stores the selected expiration option (e.g. 30/90/180/365). Null means "Never".
    credential_expiry_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
    user_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("users.id"), nullable=False)

    user = relationship("UserModel", back_populates="api_keys", foreign_keys=[user_id])
    api_key_roles = relationship("ApiKeyRoleModel", back_populates="api_key",
                                 foreign_keys="[ApiKeyRoleModel.api_key_id]")


    @property
    def roles(self):
        return [akr.role for akr in self.api_key_roles if akr.role]

    @property
    def permissions(self) -> set[str]:
        """
        Returns a set of all permission strings granted to this API key via its roles.
        """
        all_perms = set()
        for akr in self.api_key_roles:
            if akr.role:  # role is a Roles object
                # each role has a .permissions property returning a list of strings
                all_perms.update(akr.role.permissions)
        return all_perms

    def __repr__(self):
        return f"<ApiKeys(id={self.id}, name={self.name})>"

