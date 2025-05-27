from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
from app.db.base import Base

class AppSettingsModel(Base):
    __tablename__ = "app_settings"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String, nullable=False, unique=True)
    value = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    encrypted = Column(Integer, nullable=False, default=0)
