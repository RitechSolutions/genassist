import datetime
from typing import Optional
from sqlalchemy import UUID, Column, Date, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class JobLogsModel(Base):
    __tablename__ = 'job_logs'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='job_logs_pk'),
    )

    job_id: Mapped[Optional[UUID]] = mapped_column(UUID)
    job_status: Mapped[Optional[str]] = mapped_column(String(255))
    started_at: Mapped[Optional[datetime.date]] = mapped_column(Date)
    ended_at: Mapped[Optional[datetime.date]] = mapped_column(Date)
    job_params: Mapped[Optional[str]] = mapped_column(Text)
    job_result: Mapped[Optional[str]] = mapped_column(Text)
