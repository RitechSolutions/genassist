from typing import Optional
from sqlalchemy import Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
class JobModel(Base):
    __tablename__ = 'jobs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='jobs_pk'),
        UniqueConstraint('name', name='jobs_unique')
    )

    name: Mapped[Optional[str]] = mapped_column(String(255))
    container_def: Mapped[Optional[str]] = mapped_column(String(255))
    job_params: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[Optional[int]] = mapped_column(Integer)
