from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi_injector import Injected
from app.core.permissions.constants import Permissions as P
from app.auth.dependencies import auth, permissions
from app.schemas.llm import LlmAnalyst, LlmAnalystCreate, LlmAnalystUpdate
from app.services.llm_analysts import LlmAnalystService


router = APIRouter()


@router.get("", response_model=list[LlmAnalyst], dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.READ))
])
async def get_all(service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.get_all()


@router.get("/{llm_analyst_id}", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.READ))
])
async def get(llm_analyst_id: UUID, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.get_by_id(llm_analyst_id)


@router.post("", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.CREATE))
])
async def create(data: LlmAnalystCreate, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.create(data)


@router.patch("/{llm_analyst_id}", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.UPDATE))
])
async def update(llm_analyst_id: UUID, data: LlmAnalystUpdate, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.update(llm_analyst_id, data)


@router.delete("/{llm_analyst_id}", dependencies=[
    Depends(auth),
    Depends(permissions(P.LlmAnalyst.DELETE))
])
async def delete(llm_analyst_id: UUID, service: LlmAnalystService = Injected(LlmAnalystService)):
    return await service.delete(llm_analyst_id)
