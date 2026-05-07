from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AudioProvidersModel(Base):
    __tablename__ = "audio_providers"

    name: Mapped[Optional[str]] = mapped_column(String(255))
    provider_type: Mapped[Optional[str]] = mapped_column(String(50))
    capability: Mapped[Optional[str]] = mapped_column(String(10))
    connection_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    connection_status: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    is_default: Mapped[Optional[int]] = mapped_column(Integer, default=0)
