<<<<<<< HEAD
from fastapi import APIRouter, Depends
from uuid import UUID

from app.dependencies.services import get_llm_analyst_service
from app.services.llm_analysts import LlmAnalystService
from app.auth.dependencies import auth, permissions
from app.schemas.llm import LlmAnalyst, LlmAnalystCreate, LlmAnalystUpdate
=======
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth.dependencies import auth, permissions
from app.schemas.llm import LlmAnalyst, LlmAnalystCreate, LlmAnalystUpdate
from app.services.llm_analysts import LlmAnalystService

>>>>>>> development

router = APIRouter()


@router.get("/", response_model=list[LlmAnalyst], dependencies=[
    Depends(auth),
    Depends(permissions("read:llm_analyst"))
])
<<<<<<< HEAD
async def get_all(service: LlmAnalystService = Depends(get_llm_analyst_service)):
=======
async def get_all(service: LlmAnalystService = Depends()):
>>>>>>> development
    return await service.get_all()


@router.get("/{llm_analyst_id}", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions("read:llm_analyst"))
])
<<<<<<< HEAD
async def get(llm_analyst_id: UUID, service: LlmAnalystService = Depends(get_llm_analyst_service)):
=======
async def get(llm_analyst_id: UUID, service: LlmAnalystService = Depends()):
>>>>>>> development
    return await service.get_by_id(llm_analyst_id)


@router.post("/", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions("create:llm_analyst"))
])
<<<<<<< HEAD
async def create(data: LlmAnalystCreate, service: LlmAnalystService = Depends(get_llm_analyst_service)):
=======
async def create(data: LlmAnalystCreate, service: LlmAnalystService = Depends()):
>>>>>>> development
    return await service.create(data)


@router.patch("/{llm_analyst_id}", response_model=LlmAnalyst, dependencies=[
    Depends(auth),
    Depends(permissions("update:llm_analyst"))
])
<<<<<<< HEAD
async def update(llm_analyst_id: UUID, data: LlmAnalystUpdate, service: LlmAnalystService = Depends(get_llm_analyst_service)):
=======
async def update(llm_analyst_id: UUID, data: LlmAnalystUpdate, service: LlmAnalystService = Depends()):
>>>>>>> development
    return await service.update(llm_analyst_id, data)


@router.delete("/{llm_analyst_id}", dependencies=[
    Depends(auth),
    Depends(permissions("delete:llm_analyst"))
])
<<<<<<< HEAD
async def delete(llm_analyst_id: UUID, service: LlmAnalystService = Depends(get_llm_analyst_service)):
=======
async def delete(llm_analyst_id: UUID, service: LlmAnalystService = Depends()):
>>>>>>> development
    return await service.delete(llm_analyst_id)
