from typing import Optional, List
from uuid import UUID

from injector import inject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.db.models.translation import LanguageModel, TranslationKeyModel, TranslationValueModel
from app.schemas.translation import LanguageUpdate, TranslationCreate, TranslationUpdate


@inject
class LanguagesRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> List[LanguageModel]:
        result = await self.db.execute(
            select(LanguageModel).order_by(LanguageModel.code)
        )
        return list(result.scalars().all())

    async def get_active(self) -> List[LanguageModel]:
        result = await self.db.execute(
            select(LanguageModel)
            .where(LanguageModel.is_active.is_(True))
            .order_by(LanguageModel.code)
        )
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> Optional[LanguageModel]:
        result = await self.db.execute(
            select(LanguageModel).where(LanguageModel.code == code)
        )
        return result.scalars().first()

    async def create(self, code: str, name: str) -> LanguageModel:
        obj = LanguageModel(code=code, name=name)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, language_id: UUID) -> Optional[LanguageModel]:
        result = await self.db.execute(
            select(LanguageModel).where(LanguageModel.id == language_id)
        )
        return result.scalars().first()

    async def update(self, model: LanguageModel, dto: LanguageUpdate) -> LanguageModel:
        if dto.name is not None:
            model.name = dto.name
        if dto.is_active is not None:
            model.is_active = dto.is_active
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def delete(self, model: LanguageModel) -> None:
        model.is_deleted = 1
        await self.db.commit()

    async def get_code_to_id_map(self) -> dict[str, UUID]:
        langs = await self.get_active()
        return {lang.code: lang.id for lang in langs}


@inject
class TranslationsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _eager_options():
        return [
            selectinload(TranslationKeyModel.values).joinedload(
                TranslationValueModel.language
            )
        ]

    async def get_all(self) -> List[TranslationKeyModel]:
        result = await self.db.execute(
            select(TranslationKeyModel).options(*self._eager_options())
        )
        return list(result.scalars().all())

    async def get_by_key(self, key: str) -> Optional[TranslationKeyModel]:
        result = await self.db.execute(
            select(TranslationKeyModel)
            .where(TranslationKeyModel.key == key)
            .options(*self._eager_options())
        )
        return result.scalars().first()

    async def get_by_prefix(self, prefix: str) -> List[TranslationKeyModel]:
        result = await self.db.execute(
            select(TranslationKeyModel)
            .where(TranslationKeyModel.key.startswith(prefix))
            .options(*self._eager_options())
        )
        return list(result.scalars().all())

    async def create(
        self, dto: TranslationCreate, lang_code_to_id: dict[str, UUID]
    ) -> TranslationKeyModel:
        obj = TranslationKeyModel(
            key=dto.key,
            default_value=dto.default,
        )
        for lang_code, value in dto.translations.items():
            lang_id = lang_code_to_id.get(lang_code)
            if lang_id and value:
                obj.values.append(
                    TranslationValueModel(language_id=lang_id, value=value)
                )
        self.db.add(obj)
        await self.db.commit()
        # Re-fetch with eager loading to populate language relationships
        return await self.get_by_key(dto.key)  # type: ignore[return-value]

    async def update(
        self, key: str, dto: TranslationUpdate, lang_code_to_id: dict[str, UUID]
    ) -> Optional[TranslationKeyModel]:
        obj = await self.get_by_key(key)
        if not obj:
            return None

        if dto.default is not None:
            obj.default_value = dto.default

        if dto.translations is not None:
            # Build lookup of existing values by language_id
            existing_by_lang_id = {v.language_id: v for v in obj.values}

            for lang_code, value in dto.translations.items():
                lang_id = lang_code_to_id.get(lang_code)
                if not lang_id:
                    continue

                existing_val = existing_by_lang_id.get(lang_id)
                if value:
                    if existing_val:
                        existing_val.value = value
                    else:
                        obj.values.append(
                            TranslationValueModel(language_id=lang_id, value=value)
                        )
                elif existing_val:
                    # Empty string means remove this translation
                    await self.db.delete(existing_val)

        await self.db.commit()
        return await self.get_by_key(key)

    async def delete_by_key(self, key: str) -> bool:
        obj = await self.get_by_key(key)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
