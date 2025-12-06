from injector import inject
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from uuid import UUID
from app.core.utils.bi_utils import get_masked_api_key
from app.core.utils.encryption_utils import encrypt_key
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.llm import LlmProviderCreate, LlmProviderUpdate

@inject
class LlmProviderService:
    def __init__(self, repository: LlmProviderRepository):
        self.repository = repository


    async def create(self, data: LlmProviderCreate):
        connection_data = data.connection_data.copy()

        api_key = connection_data.get("api_key")
        if api_key:
            encrypted = encrypt_key(api_key)
            masked = get_masked_api_key(api_key)
            connection_data["api_key"] = encrypted
            connection_data["masked_api_key"] = masked
        # else:
        #     raise AppException(error_key=ErrorKey.MISSING_API_KEY_LLM_PROVIDER)
        
        data.connection_data = connection_data
        model = await self.repository.create(data)
        return model


    async def get_by_id(self, llm_provider_id: UUID):
        obj = await self.repository.get_by_id(llm_provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.LLM_PROVIDER_NOT_FOUND, status_code=404)
        return obj


    async def get_all(self):
        models = await self.repository.get_all()
        return models


    async def update(self, llm_provider_id: UUID, data: LlmProviderUpdate):
        obj = await self.repository.get_by_id(llm_provider_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, field, value)
        model = await self.repository.update(obj)
        return model


    async def delete(self, llm_provider_id: UUID):
        obj = await self.repository.get_by_id(llm_provider_id)
        await self.repository.delete(obj)
        return {"message": f"Deleted LLM Provider with ID {llm_provider_id}"}
