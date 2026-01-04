# app/db/models/webhook.py
from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from enum import Enum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

# Base class for declarative models
from app.db.base import Base


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"


class WebhookType(str, Enum):
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    GENERIC = "generic"


class WebhookModel(Base):
    """
    SQLAlchemy model for a Webhook.
    Uses UUID as the primary key and stores webhook definition details.
    """

    __tablename__ = "webhooks"

    name = Column(String, unique=True, index=True, nullable=False)
    url = Column(String, nullable=False)
    method = Column(String, nullable=False)  # e.g., 'POST' , 'GET'
    headers = Column(JSONB, default={}, nullable=False)  # Stores dictionary of headers
    secret = Column(String, nullable=True)  # if null alow public calls

    is_deleted = Column(Integer, nullable=False, default=0)
    is_active = Column(Integer, nullable=False, default=1)
    description = Column(String, nullable=True)
    webhook_type = Column(
        String, nullable=False, default="generic"
    )  # slack, whatsapp, generic
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    app_settings_id = Column(
        UUID(as_uuid=True), ForeignKey("app_settings.id"), nullable=True
    )

    agent = relationship("AgentModel", uselist=False)
    app_settings = relationship("AppSettingsModel", uselist=False)

    def __repr__(self):
        return f"<WebhookModel(id='{self.id}', name='{self.name}', url='{self.url}', type='{self.webhook_type}')>"
