import logging
from uuid import UUID

from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from injector import inject

from app.cache.redis_cache import make_key_builder
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.fallback_chains import FallbackChainRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.fallback_chain import (
    FallbackChainCreate,
    FallbackChainMinimal,
    FallbackChainRead,
    FallbackChainUpdate,
)

logger = logging.getLogger(__name__)

fallback_chain_id_key_builder = make_key_builder("fallback_chain_id")
fallback_chain_all_key_builder = make_key_builder("-")


@inject
class FallbackChainService:
    def __init__(self, repository: FallbackChainRepository, llm_provider_repository: LlmProviderRepository):
        self.repository = repository
        self.llm_provider_repository = llm_provider_repository

    async def _provider_exists(self, pid) -> bool:
        try:
            obj = await self.llm_provider_repository.get_by_id(UUID(str(pid)))
        except (ValueError, TypeError):
            obj = None
        return bool(obj)

    async def _validate_provider_ids(self, provider_ids: list[str] | None):
        """Reject chains that reference providers which don't exist (used on create)."""
        for pid in provider_ids or []:
            if not await self._provider_exists(pid):
                raise AppException(
                    error_key=ErrorKey.FALLBACK_CHAIN_INVALID_PROVIDER,
                    status_code=400,
                    error_detail=str(pid),
                )

    async def _prune_missing_providers(self, update_data: dict) -> None:
        """Drop provider ids (and their timeout overrides) that no longer exist.

        Used on update so a chain whose provider was deleted out from under it can
        still be edited/saved instead of being blocked by strict validation.
        Mutates update_data in place.
        """
        if "provider_ids" not in update_data:
            return
        kept: list[str] = []
        for pid in update_data["provider_ids"] or []:
            if await self._provider_exists(pid):
                kept.append(str(pid))
        update_data["provider_ids"] = kept

        retry_policy = update_data.get("retry_policy")
        if isinstance(retry_policy, dict):
            pt = retry_policy.get("provider_timeouts")
            if isinstance(pt, dict):
                retry_policy["provider_timeouts"] = {
                    k: v for k, v in pt.items() if k in kept
                }

    async def chains_referencing_provider(self, provider_id) -> list[str]:
        """Return the names of active chains that reference the given provider id."""
        pid = str(provider_id)
        chains = await self.repository.get_all()
        return [
            (c.name or str(c.id))
            for c in chains
            if pid in [str(x) for x in (c.provider_ids or [])]
        ]

    @staticmethod
    def _dump(data) -> dict:
        """Serialize a pydantic create/update model to a column dict for the ORM."""
        payload = data.model_dump(exclude_unset=True, mode="json")
        # retry_policy nests under a RetryPolicy model; mode="json" already turns it
        # into a plain dict, which is what the JSONB column stores.
        return payload

    async def create(self, data: FallbackChainCreate):
        await self._validate_provider_ids(data.provider_ids)
        payload = self._dump(data)
        return await self.repository.create(payload)

    @cache(
        expire=300,
        namespace="fallback_chains:get_by_id",
        key_builder=fallback_chain_id_key_builder,
        coder=PickleCoder,
    )
    async def get_by_id(self, chain_id: UUID):
        obj = await self.repository.get_by_id(chain_id)
        if not obj:
            raise AppException(error_key=ErrorKey.FALLBACK_CHAIN_NOT_FOUND, status_code=404)
        return FallbackChainRead.model_validate(obj)

    @cache(
        expire=300,
        namespace="fallback_chains:get_all",
        key_builder=fallback_chain_all_key_builder,
        coder=PickleCoder,
    )
    async def get_all(self):
        models = await self.repository.get_all()
        return [FallbackChainRead.model_validate(obj) for obj in models]

    async def get_all_minimal(self) -> list[FallbackChainMinimal]:
        rows = await self.repository.get_all_minimal()
        return [FallbackChainMinimal.model_validate(r, from_attributes=True) for r in rows]

    async def update(self, chain_id: UUID, data: FallbackChainUpdate):
        obj = await self.repository.get_by_id(chain_id)
        if not obj:
            raise AppException(error_key=ErrorKey.FALLBACK_CHAIN_NOT_FOUND, status_code=404)

        update_data = self._dump(data)
        # Prune references to providers that were deleted so the edit isn't blocked
        # by a stale id the user never touched.
        await self._prune_missing_providers(update_data)

        for field, value in update_data.items():
            setattr(obj, field, value)

        return await self.repository.update(obj)

    async def delete(self, chain_id: UUID):
        obj = await self.repository.get_by_id(chain_id)
        if not obj:
            raise AppException(error_key=ErrorKey.FALLBACK_CHAIN_NOT_FOUND, status_code=404)
        await self.repository.delete(obj)
        return {"message": f"Deleted fallback chain with ID {chain_id}"}
