from typing import Optional, List, Sequence

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.translation import TranslationModel
from app.schemas.translation import TranslationCreate, TranslationUpdate


@inject
class TranslationsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, dto: TranslationCreate) -> TranslationModel:
        obj = TranslationModel(**dto.model_dump())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_all(self) -> List[TranslationModel]:
        result = await self.db.execute(select(TranslationModel))
        rows: Sequence[TranslationModel] = result.scalars().all()
        return list(rows)

    async def get_by_key(self, key: str) -> Optional[TranslationModel]:
        result = await self.db.execute(
            select(TranslationModel).where(TranslationModel.key == key)
        )
        return result.scalars().first()

    async def update(self, key: str, dto: TranslationUpdate) -> Optional[TranslationModel]:
        obj = await self.get_by_key(key)
        if not obj:
            return None

        for field, val in dto.model_dump(exclude_unset=True).items():
            setattr(obj, field, val)

        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, key: str) -> bool:
        obj = await self.get_by_key(key)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
