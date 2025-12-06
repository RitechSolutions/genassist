import datetime
from typing import Optional

from sqlalchemy import UUID, DateTime, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
class RecordingModel(Base):
    __tablename__ = 'recordings'
    __table_args__ = (
        PrimaryKeyConstraint('id', name='recordings_pkey'),
    )

    file_path: Mapped[str] = mapped_column(String(1024))
    original_filename: Mapped[str] = mapped_column(String(1024))


    data_source_id: Mapped[Optional[UUID]]  = mapped_column(UUID)
    operator_id: Mapped[UUID] = mapped_column(UUID)
    recording_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    conversation = relationship("ConversationModel", back_populates="recording", uselist=False)