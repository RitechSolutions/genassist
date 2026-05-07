from uuid import UUID

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.audio_provider import AudioProvidersModel


@inject
class AudioProviderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data) -> AudioProvidersModel:
        obj = AudioProvidersModel(**data.model_dump())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, provider_id: UUID) -> AudioProvidersModel | None:
        return await self.db.get(AudioProvidersModel, provider_id)

    async def update(self, obj: AudioProvidersModel) -> AudioProvidersModel:
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: AudioProvidersModel):
        obj.is_deleted = 1
        self.db.add(obj)
        await self.db.commit()

    async def get_all(self):
        result = await self.db.execute(
            select(AudioProvidersModel)
            .where(AudioProvidersModel.is_deleted == 0)
            .order_by(AudioProvidersModel.created_at.asc())
        )
        return result.scalars().all()

    async def get_all_by_capability(self, capability: str):
        result = await self.db.execute(
            select(AudioProvidersModel)
            .where(
                AudioProvidersModel.is_deleted == 0,
                (AudioProvidersModel.capability == capability)
                | (AudioProvidersModel.capability == "both"),
            )
            .order_by(AudioProvidersModel.created_at.asc())
        )
        return result.scalars().all()

    async def get_all_minimal(self):
        stmt = (
            select(
                AudioProvidersModel.id,
                AudioProvidersModel.name,
                AudioProvidersModel.provider_type,
                AudioProvidersModel.capability,
                AudioProvidersModel.is_active,
            )
            .where(AudioProvidersModel.is_deleted == 0)
            .order_by(AudioProvidersModel.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return result.all()
