from typing import List, Optional

from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from injector import inject

from app.cache.redis_cache import make_key_builder, invalidate_cache
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.translations import LanguagesRepository, TranslationsRepository
from app.schemas.translation import (
    LanguageCreate,
    LanguageRead,
    TranslationCreate,
    TranslationRead,
    TranslationUpdate,
)


translation_key_builder = make_key_builder("key")  # type: ignore[assignment]
translation_all_key_builder = make_key_builder("-")  # type: ignore[assignment]
language_all_key_builder = make_key_builder("-")  # type: ignore[assignment]


def _model_to_read(row) -> TranslationRead:
    """Convert a TranslationKeyModel (with eagerly loaded values) to TranslationRead."""
    translations = {v.language.code: v.value for v in row.values}
    return TranslationRead(
        id=row.id,
        key=row.key,
        default=row.default_value,
        translations=translations,
    )


@inject
class LanguagesService:
    def __init__(self, repository: LanguagesRepository):
        self.repository = repository

    @cache(
        expire=300,
        namespace="languages:get_all",
        key_builder=language_all_key_builder,
        coder=PickleCoder,
    )
    async def get_all(self) -> List[LanguageRead]:
        rows = await self.repository.get_active()
        return [LanguageRead.model_validate(r, from_attributes=True) for r in rows]

    async def create(self, dto: LanguageCreate) -> LanguageRead:
        existing = await self.repository.get_by_code(dto.code)
        if existing:
            raise AppException(
                status_code=400, error_key=ErrorKey.TRANSLATION_ALREADY_EXISTS
            )
        row = await self.repository.create(dto.code, dto.name)
        await invalidate_cache("languages:get_all", None)
        return LanguageRead.model_validate(row, from_attributes=True)


@inject
class TranslationsService:
    def __init__(
        self,
        repository: TranslationsRepository,
        languages_repository: LanguagesRepository,
    ):
        self.repository = repository
        self.languages_repository = languages_repository

    async def create(self, dto: TranslationCreate) -> TranslationRead:
        existing = await self.repository.get_by_key(dto.key)
        if existing:
            raise AppException(
                status_code=400, error_key=ErrorKey.TRANSLATION_ALREADY_EXISTS
            )
        lang_map = await self.languages_repository.get_code_to_id_map()
        row = await self.repository.create(dto, lang_map)
        await invalidate_cache("translations:get_all", None)
        return _model_to_read(row)

    @cache(
        expire=300,
        namespace="translations:get_all",
        key_builder=translation_all_key_builder,
        coder=PickleCoder,
    )
    async def get_all(self) -> List[TranslationRead]:
        rows = await self.repository.get_all()
        return [_model_to_read(r) for r in rows]

    async def get_by_key(self, key: str) -> TranslationRead:
        lookup = await self._get_all_as_dict()
        if key in lookup:
            return lookup[key]
        raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)

    async def _get_all_as_dict(self) -> dict[str, TranslationRead]:
        """Build a dict keyed by translation key from the cached list."""
        rows = await self.get_all()
        return {r.key: r for r in rows}

    async def get_by_key_lang(
        self,
        key: str,
        accept_language: Optional[str],
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve a translation value for a given key and `Accept-Language` header.
        """
        if default is None or default == "":
            return None

        lang_code: Optional[str] = None
        if accept_language:
            primary_token = accept_language.split(",")[0].strip()
            if primary_token:
                lang_code = primary_token.split("-")[0].lower()

        try:
            translation = await self.get_by_key(key)
        except AppException as exc:
            if exc.status_code == 404:
                return default
            raise

        if lang_code:
            value = translation.translations.get(lang_code)
            if value:
                return value

        if translation.default:
            return translation.default

        return default

    async def resolve_many(
        self,
        items: dict[str, Optional[str]],
        accept_language: Optional[str],
    ) -> dict[str, Optional[str]]:
        """
        Batch-resolve multiple translation keys in one pass over the cached list.
        `items` maps translation key -> default value.
        """
        lang_code: Optional[str] = None
        if accept_language:
            primary_token = accept_language.split(",")[0].strip()
            if primary_token:
                lang_code = primary_token.split("-")[0].lower()

        lookup = await self._get_all_as_dict()
        result: dict[str, Optional[str]] = {}

        for key, default in items.items():
            if default is None or default == "":
                result[key] = None
                continue

            translation = lookup.get(key)
            if translation is None:
                result[key] = default
                continue

            if lang_code:
                value = translation.translations.get(lang_code)
                if value:
                    result[key] = value
                    continue

            if translation.default:
                result[key] = translation.default
            else:
                result[key] = default

        return result

    async def update(self, key: str, dto: TranslationUpdate) -> TranslationRead:
        existing = await self.repository.get_by_key(key)
        if not existing:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        lang_map = await self.languages_repository.get_code_to_id_map()
        updated = await self.repository.update(key, dto, lang_map)
        await invalidate_cache("translations:get_all", None)
        return _model_to_read(updated)

    async def delete(self, key: str) -> None:
        existing = await self.repository.get_by_key(key)
        if not existing:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.repository.delete_by_key(key)
        await invalidate_cache("translations:get_all", None)

    async def get_languages_for_prefix(self, prefix: str) -> List[str]:
        """
        Return language codes that have at least one non-empty translation
        for keys matching the given prefix.
        """
        rows = await self.repository.get_by_prefix(prefix)
        found: set[str] = set()

        for row in rows:
            for val in row.values:
                if val.value and val.value.strip():
                    found.add(val.language.code)

        # Return in sorted order for stability
        return sorted(found)
