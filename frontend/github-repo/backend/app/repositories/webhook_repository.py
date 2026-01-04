from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import HttpUrl
from sqlalchemy.orm import joinedload
from app.db.models.agent import AgentModel
from app.db.models.webhook import WebhookModel
from app.schemas.webhook import WebhookBase, WebhookUpdate
from sqlalchemy.future import select
from injector import inject
import logging

logger = logging.getLogger(__name__)


@inject
class WebhookRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, webhook_data: WebhookBase, webhook_id: Optional[UUID] = None
    ) -> WebhookModel:
        """Create a new webhook definition."""
        webhook = WebhookModel(
            name=webhook_data.name,
            url=str(webhook_data.url),
            method=webhook_data.method,
            headers=webhook_data.headers,
            secret=webhook_data.secret,
            description=webhook_data.description,
            is_active=webhook_data.is_active,
            webhook_type=webhook_data.webhook_type,
            agent_id=webhook_data.agent_id,
            app_settings_id=webhook_data.app_settings_id,
        )

        if webhook_id:
            webhook.id = webhook_id

        self.db.add(webhook)
        await self.db.commit()
        await self.db.refresh(webhook)
        return webhook

    async def get_by_id(self, webhook_id: UUID) -> Optional[WebhookModel]:
        """Fetch webhook definition by ID."""
        query = select(WebhookModel).where(
            WebhookModel.id == webhook_id and WebhookModel.is_deleted == 0
        )
        result = await self.db.execute(query)
        webhook = result.scalars().first()

        return webhook

    async def get_by_id_full(self, webhook_id: UUID) -> WebhookModel | None:
        """Fetch webhook definition by ID with full agent and app settings."""
        result = await self.db.execute(
            select(WebhookModel)
            .options(
                joinedload(WebhookModel.agent).joinedload(AgentModel.operator),
                joinedload(WebhookModel.app_settings),
            )
            .where(WebhookModel.id == webhook_id)
        )
        return result.scalars().first()

    async def get_all(self) -> list[WebhookModel]:
        """Fetch all webhook definitions."""
        query = (
            select(WebhookModel)
            .where(WebhookModel.is_deleted == 0)
            .order_by(WebhookModel.created_at.asc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(
        self, webhook_id: UUID, updates: WebhookUpdate
    ) -> Optional[WebhookModel]:
        webhook = await self.get_by_id(webhook_id)
        if not webhook:
            return None

        for key, value in updates.model_dump(exclude_unset=True).items():
            clean_value = str(value) if isinstance(value, (HttpUrl, UUID)) else value
            setattr(webhook, key, clean_value)

        await self.db.commit()
        await self.db.refresh(webhook)
        return webhook

    async def delete(self, webhook_id: UUID) -> bool:
        """Soft-Delete a webhook definition."""
        webhook = await self.get_by_id(webhook_id)
        if not webhook:
            return False
        webhook.is_deleted = 1
        # await self.db.delete(webhook) # Only Soft Delete
        await self.db.commit()
        await self.db.refresh(webhook)
        return True
