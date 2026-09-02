"""Tenant-registered LLM models.

The built-in option lists in ``LLM_FORM_SCHEMAS`` stay the source of truth for
everything shipped with the product. This service manages the per-tenant *overlay*
of extra models and produces the additions that ``LLMProvider`` appends to the
provider form at request time.
"""

import logging
from uuid import UUID

from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.llm_model_catalog import LlmModelCatalogModel
from app.repositories.llm_model_catalog import LlmModelCatalogRepository
from app.schemas.dynamic_form_schemas import LLM_FORM_SCHEMAS
from app.schemas.llm_model_catalog import (
    LlmModelCatalogCreate,
    LlmModelCatalogProvider,
    LlmModelCatalogRead,
    LlmModelCatalogUpdate,
)

logger = logging.getLogger(__name__)

MODEL_FIELD_NAME = "model"

# The vLLM fine-tune option list is replaced wholesale with the deployments that are
# currently running, so re-adding a stale value would offer a dead deployment.
_NO_IN_USE_UNION = frozenset({"vllm_fine_tuned"})


def _model_field(provider_key: str):
    """The ``model`` FieldSchema of a built-in provider type, or None."""
    schema = LLM_FORM_SCHEMAS.get(provider_key)
    if not schema or not schema.fields:
        return None
    for field in schema.fields:
        if field.name == MODEL_FIELD_NAME:
            return field
    return None


def builtin_model_keys(provider_key: str) -> set[str]:
    field = _model_field(provider_key)
    if not field or not field.options:
        return set()
    return {opt.get("value") for opt in field.options if opt.get("value")}


@inject
class LlmModelCatalogService:
    def __init__(self, repo: LlmModelCatalogRepository):
        self.repo = repo

    # ───────────── management screen ─────────────

    async def list_entries(self) -> list[LlmModelCatalogRead]:
        rows = await self.repo.list_all()
        return [self._to_read(row) for row in rows]

    def list_providers(self) -> list[LlmModelCatalogProvider]:
        """Provider types that expose a model field, with the models already built in."""
        providers: list[LlmModelCatalogProvider] = []
        for provider_key, schema in LLM_FORM_SCHEMAS.items():
            if _model_field(provider_key) is None:
                continue
            providers.append(
                LlmModelCatalogProvider(
                    provider_key=provider_key,
                    name=schema.name,
                    builtin_model_keys=sorted(builtin_model_keys(provider_key)),
                )
            )
        providers.sort(key=lambda p: p.name.lower())
        return providers

    async def create_entry(self, dto: LlmModelCatalogCreate) -> LlmModelCatalogRead:
        self._assert_extendable_provider(dto.provider_key)

        existing = await self.repo.get_by_provider_model(dto.provider_key, dto.model_key)
        if existing:
            raise AppException(error_key=ErrorKey.LLM_CATALOG_MODEL_ALREADY_EXISTS, status_code=409)

        created = await self.repo.create(
            LlmModelCatalogModel(
                provider_key=dto.provider_key,
                model_key=dto.model_key,
                label=dto.label,
                is_active=dto.is_active,
            )
        )
        return self._to_read(created)

    async def update_entry(
        self, entry_id: UUID, dto: LlmModelCatalogUpdate
    ) -> LlmModelCatalogRead | None:
        row = await self.repo.get_active_by_id(entry_id)
        if not row:
            return None
        if dto.label is not None:
            row.label = dto.label.strip()
        if dto.is_active is not None:
            row.is_active = dto.is_active
        updated = await self.repo.update(row)
        return self._to_read(updated)

    async def delete_entry(self, entry_id: UUID) -> bool:
        return await self.repo.soft_delete_by_id(entry_id)

    # ───────────── provider form overlay ─────────────

    async def build_option_overlay(self) -> dict[str, list[dict[str, str]]]:
        """Extra ``{"value", "label"}`` options per provider type, in display order.

        Combines tenant-registered models with any model a configured provider is
        already using, so editing a provider never shows an empty Model dropdown.
        Callers append these after the built-in options and drop duplicates.
        """
        overlay: dict[str, list[dict[str, str]]] = {}

        for row in await self.repo.list_active():
            provider_key = (row.provider_key or "").strip().lower()
            model_key = (row.model_key or "").strip()
            if not provider_key or not model_key:
                continue
            overlay.setdefault(provider_key, []).append(
                {"value": model_key, "label": row.label or model_key}
            )

        for provider_key, model_key in await self.repo.list_models_in_use():
            provider_key = (provider_key or "").strip().lower()
            model_key = (model_key or "").strip()
            if not provider_key or not model_key or provider_key in _NO_IN_USE_UNION:
                continue
            field = _model_field(provider_key)
            # Only patch dropdowns that already list options; a free-text model field
            # needs no help, and turning one into a datalist would change the UI.
            if not field or field.type != "select" or not field.options:
                continue
            if model_key in builtin_model_keys(provider_key):
                continue
            already = {opt["value"] for opt in overlay.get(provider_key, [])}
            if model_key in already:
                continue
            overlay.setdefault(provider_key, []).append(
                {"value": model_key, "label": model_key}
            )

        return overlay

    # ───────────── helpers ─────────────

    def _assert_extendable_provider(self, provider_key: str) -> None:
        if provider_key not in LLM_FORM_SCHEMAS:
            raise AppException(
                error_key=ErrorKey.LLM_CATALOG_UNKNOWN_PROVIDER,
                status_code=400,
                error_variables=[provider_key],
            )
        if _model_field(provider_key) is None:
            raise AppException(
                error_key=ErrorKey.LLM_CATALOG_PROVIDER_HAS_NO_MODEL_FIELD,
                status_code=400,
                error_variables=[provider_key],
            )

    @staticmethod
    def _to_read(row: LlmModelCatalogModel) -> LlmModelCatalogRead:
        read = LlmModelCatalogRead.model_validate(row, from_attributes=True)
        read.is_shadowed_by_builtin = row.model_key in builtin_model_keys(
            (row.provider_key or "").strip().lower()
        )
        return read
