from typing import Optional
from sqlalchemy import Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CustomerModel(Base):
    __tablename__ = 'customers'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='customers_pk'),
    )

    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(100))
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
    source_ref: Mapped[Optional[str]] = mapped_column(String(255))

