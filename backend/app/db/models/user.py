from typing import Optional
from sqlalchemy import DateTime, Integer, PrimaryKeyConstraint, String, UniqueConstraint, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING
from uuid import UUID
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.role import RoleModel



class UserModel(Base):
    __tablename__ = 'users'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='users_pkey'),
        UniqueConstraint('username', name='users_username_key')
    )
    username: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
    hashed_password: Mapped[str] = mapped_column(String(1000))
    force_upd_pass_date = mapped_column(DateTime(timezone=True)) # date to force password update

    user_type_id: Mapped[UUID] = mapped_column(ForeignKey("user_types.id"), nullable=False)

    user_roles = relationship("UserRoleModel", back_populates="user", foreign_keys="[UserRoleModel.user_id]")
    user_type = relationship("UserTypeModel", back_populates="users", foreign_keys=[user_type_id])
    api_keys = relationship("ApiKeyModel", back_populates="user", foreign_keys="[ApiKeyModel.user_id]")
    operator = relationship("OperatorModel", back_populates="user", uselist=False, foreign_keys="["
                                                                                                "OperatorModel.user_id]")
    workflows = relationship("WorkflowModel", back_populates="user", foreign_keys="[WorkflowModel.user_id]")

    @property
    def roles(self) -> list["RoleModel"]:
        """
        For convenience, returns a list of the *role names* associated with this user.
        e.g., ["admin", "editor"] if you store those in Roles.name
        """
        return [ur.role for ur in self.user_roles if ur.role]


    @property
    def permissions(self) -> set[str]:
        """
        Collects all permission names from:
          - The user's roles
          - The roles attached to any of the user's API keys
        """
        perms = set()

        # 1) Grab permissions from direct user roles
        for ur in self.user_roles:
            if ur.role and ur.role.role_permissions:
                for rp in ur.role.role_permissions:
                    if rp.permission and rp.permission.is_active:
                        perms.add(rp.permission.name)

        # 2) Grab permissions from roles attached to this user's API keys
        for apikey in self.api_keys:
            for akr in apikey.api_key_roles:
                if akr.role and akr.role.role_permissions:
                    for rp in akr.role.role_permissions:
                        if rp.permission and rp.permission.is_active:
                            perms.add(rp.permission.name)

        return perms

    def __repr__(self):
        return f"<Users(id={self.id}, username={self.username})>"