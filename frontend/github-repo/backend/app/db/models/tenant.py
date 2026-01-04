from typing import Optional
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class TenantModel(Base):
    __tablename__ = 'tenants'

    # Tenant identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # Database configuration
    database_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Tenant status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional tenant-specific settings
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subdomain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name}, slug={self.slug})>"
