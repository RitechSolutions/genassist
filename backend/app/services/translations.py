from typing import List, Optional
from uuid import UUID

from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from injector import inject

from app.cache.redis_cache import make_key_builder, invalidate_cache
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.translation import TranslationKeyModel
from app.repositories.translations import LanguagesRepository, TranslationsRepository
from app.schemas.translation import (
    LanguageCreate,
    LanguageRead,
    LanguageUpdate,
    TranslationCreate,
    TranslationRead,
    TranslationUpdate,
)


translation_key_builder = make_key_builder("key")  # type: ignore[assignment]
translation_all_key_builder = make_key_builder("-")  # type: ignore[assignment]
language_all_key_builder = make_key_builder("-")  # type: ignore[assignment]


def _parse_lang_code(accept_language: Optional[str]) -> Optional[str]:
    """Extract primary language code from an Accept-Language header value."""
    if not accept_language:
        return None
    primary_token = accept_language.split(",")[0].strip()
    if not primary_token:
        return None
    return primary_token.split("-")[0].lower()


def _model_to_read(row: TranslationKeyModel) -> TranslationRead:
    """Convert a TranslationKeyModel (with eagerly loaded values) to TranslationRead."""
    translations = {v.language.code: v.value for v in row.values}
    return TranslationRead(
        id=row.id,
        key=row.key,
        default=row.default_value,
        translations=translations,
    )


def _resolve_single(
    translation: Optional[TranslationRead],
    lang_code: Optional[str],
    default: Optional[str],
) -> Optional[str]:
    """Resolve a single translation value with fallback chain."""
    if default is None or default == "":
        return None

    if translation is None:
        return default

    if lang_code:
        value = translation.translations.get(lang_code)
        if value:
            return value

    if translation.default:
        return translation.default

    return default


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

    async def get_all_admin(self) -> List[LanguageRead]:
        rows = await self.repository.get_all()
        return [LanguageRead.model_validate(r, from_attributes=True) for r in rows]

    async def update(self, language_id: UUID, dto: LanguageUpdate) -> LanguageRead:
        model = await self.repository.get_by_id(language_id)
        if not model:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        updated = await self.repository.update(model, dto)
        await invalidate_cache("languages:get_all", None)
        return LanguageRead.model_validate(updated, from_attributes=True)

    async def delete(self, language_id: UUID) -> None:
        model = await self.repository.get_by_id(language_id)
        if not model:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await self.repository.delete(model)
        await invalidate_cache("languages:get_all", None)

    async def create(self, dto: LanguageCreate) -> LanguageRead:
        existing = await self.repository.get_by_code(dto.code)
        if existing:
            raise AppException(
                status_code=400, error_key=ErrorKey.LANGUAGE_ALREADY_EXISTS
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
        """Resolve a translation value for a given key and Accept-Language header."""
        if default is None or default == "":
            return None

        lang_code = _parse_lang_code(accept_language)

        try:
            translation = await self.get_by_key(key)
        except AppException as exc:
            if exc.status_code == 404:
                return default
            raise

        return _resolve_single(translation, lang_code, default)

    async def resolve_many(
        self,
        items: dict[str, Optional[str]],
        accept_language: Optional[str],
    ) -> dict[str, Optional[str]]:
        """
        Batch-resolve multiple translation keys in one pass over the cached list.
        `items` maps translation key -> default value.
        """
        lang_code = _parse_lang_code(accept_language)
        lookup = await self._get_all_as_dict()
        return {
            key: _resolve_single(lookup.get(key), lang_code, default)
            for key, default in items.items()
        }

    async def resolve_many_for_lang(
        self,
        items: dict[str, Optional[str]],
        lang_code: Optional[str],
    ) -> dict[str, Optional[str]]:
        """
        Like resolve_many, but uses an explicit BCP-47 primary tag (e.g. "es") instead of
        parsing Accept-Language. Pass None to use translation defaults / agent fallbacks only.
        """
        normalized: Optional[str] = None
        if lang_code and str(lang_code).strip():
            normalized = str(lang_code).strip().split("-")[0].lower()
        lookup = await self._get_all_as_dict()
        return {
            key: _resolve_single(lookup.get(key), normalized, default)
            for key, default in items.items()
        }

    async def update(self, key: str, dto: TranslationUpdate) -> TranslationRead:
        lang_map = await self.languages_repository.get_code_to_id_map()
        updated = await self.repository.update(key, dto, lang_map)
        if not updated:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await invalidate_cache("translations:get_all", None)
        return _model_to_read(updated)

    async def delete(self, key: str) -> None:
        deleted = await self.repository.delete_by_key(key)
        if not deleted:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        await invalidate_cache("translations:get_all", None)

    async def get_languages_for_prefix(self, prefix: str) -> List[str]:
        """
        Return language codes that have at least one non-empty translation
        for keys matching the given prefix. Uses the cached translation list.
        """
        all_translations = await self.get_all()
        found: set[str] = set()
        for t in all_translations:
            if t.key.startswith(prefix):
                for code, value in t.translations.items():
                    if value and value.strip():
                        found.add(code)
        return sorted(found)
