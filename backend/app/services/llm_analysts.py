from uuid import UUID
from fastapi import Depends
from fastapi_injector import Injected
from injector import inject

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.repositories.llm_analysts import LlmAnalystRepository
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.llm import LlmAnalystCreate, LlmAnalystUpdate

@inject
class LlmAnalystService:
    def __init__(self, repository: LlmAnalystRepository, llm_provider_repository: LlmProviderRepository  = Injected(LlmProviderRepository)):
        self.repository = repository
        self.llm_provider_repository = llm_provider_repository

    async def create(self, data: LlmAnalystCreate):
        # Check if the LLM provider exists
        obj = await self.llm_provider_repository.get_by_id(data.llm_provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.LLM_PROVIDER_NOT_FOUND, status_code=404)
        
        llm_analyst =  await self.repository.create(data)
        model = await self.repository.get_by_id(llm_analyst.id)
        return model

    async def get_by_id(self, llm_analyst_id: UUID):
        obj = await self._read_by_id(llm_analyst_id)
        return obj

    async def _read_by_id(self, llm_analyst_id: UUID):
        obj = await self.repository.get_by_id(llm_analyst_id)
        if not obj:
            raise AppException(error_key=ErrorKey.LLM_ANALYST_NOT_FOUND, status_code=404)
        return obj

    async def get_all(self):
        models = await self.repository.get_all()
        return models

    async def update(self, llm_analyst_id: UUID, data: LlmAnalystUpdate):
        obj = await self._read_by_id(llm_analyst_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        model = await self.repository.update(obj)
        return model

    async def delete(self, llm_analyst_id: UUID):
        obj = await self._read_by_id(llm_analyst_id)
        await self.repository.delete(obj)
        return {"message": f"LlmAnalyst with ID {llm_analyst_id} has been deleted."}
