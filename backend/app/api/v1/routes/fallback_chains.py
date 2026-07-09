from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected

from app.auth.dependencies import auth, permissions
from app.cache.redis_cache import invalidate_fallback_chain_cache
from app.core.permissions.constants import Permissions as P
from app.schemas.fallback_chain import (
    FallbackChainCreate,
    FallbackChainMinimal,
    FallbackChainRead,
    FallbackChainUpdate,
)
from app.services.fallback_chains import FallbackChainService

router = APIRouter()


@router.get(
    "",
    response_model=list[FallbackChainRead],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_all(service: FallbackChainService = Injected(FallbackChainService)):
    return await service.get_all()


@router.get(
    "/minimal",
    response_model=list[FallbackChainMinimal],
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get_all_minimal(service: FallbackChainService = Injected(FallbackChainService)):
    return await service.get_all_minimal()


@router.get(
    "/{chain_id}",
    response_model=FallbackChainRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.READ))],
)
async def get(chain_id: UUID, service: FallbackChainService = Injected(FallbackChainService)):
    return await service.get_by_id(chain_id)


@router.post(
    "",
    response_model=FallbackChainRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.CREATE))],
)
async def create(
    data: FallbackChainCreate,
    service: FallbackChainService = Injected(FallbackChainService),
):
    res = await service.create(data)
    await invalidate_fallback_chain_cache(chain_id=None)
    return res


@router.patch(
    "/{chain_id}",
    response_model=FallbackChainRead,
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.UPDATE))],
)
async def update(
    chain_id: UUID,
    data: FallbackChainUpdate,
    service: FallbackChainService = Injected(FallbackChainService),
):
    res = await service.update(chain_id, data)
    await invalidate_fallback_chain_cache(chain_id=chain_id)
    return res


@router.delete(
    "/{chain_id}",
    dependencies=[Depends(auth), Depends(permissions(P.LlmProvider.DELETE))],
)
async def delete(
    chain_id: UUID,
    service: FallbackChainService = Injected(FallbackChainService),
):
    res = await service.delete(chain_id)
    await invalidate_fallback_chain_cache(chain_id=chain_id)
    return res
