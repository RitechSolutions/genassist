import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from injector import inject

from app.cache.redis_cache import make_key_builder
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.bi_utils import get_masked_api_key
from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from app.repositories.llm_providers import LlmProviderRepository
from app.schemas.llm import LlmProviderCreate, LlmProviderRead, LlmProviderUpdate

logger = logging.getLogger(__name__)

llm_provider_id_key_builder = make_key_builder("llm_provider_id")
llm_provider_all_key_builder = make_key_builder("-")


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

    @cache(
        expire=300,
        namespace="llm_providers:get_by_id",
        key_builder=llm_provider_id_key_builder,
        coder=PickleCoder,
    )
    async def get_by_id(self, llm_provider_id: UUID):
        obj = await self.repository.get_by_id(llm_provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.LLM_PROVIDER_NOT_FOUND, status_code=404)
        return LlmProviderRead.model_validate(obj)

    @cache(
        expire=300,
        namespace="llm_providers:get_all",
        key_builder=llm_provider_all_key_builder,
        coder=PickleCoder,
    )
    async def get_all(self):
        models = await self.repository.get_all()
        models = [LlmProviderRead.model_validate(obj) for obj in models]
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

    async def get_default(self):
        # Get the default model (first config or default)
        models: List[LlmProviderRead] = await self.get_all()
        if not models:
            raise AppException(error_key=ErrorKey.NO_LLM_PROVIDER_CONFIGURATION_FOUND, status_code=500)
        default_model = next((m for m in models if m.is_default == 1), models[0])
        return default_model

    async def test_connection(
        self,
        llm_model_provider: Optional[str],
        connection_data: Optional[Dict[str, Any]],
        provider_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        cd = dict(connection_data or {})

        if provider_id:
            stored_raw = await self.repository.get_by_id(provider_id)
            raw_conn = dict((stored_raw.connection_data if stored_raw else None) or {})
            decrypted_conn = dict(raw_conn)
            if "api_key" in decrypted_conn and decrypted_conn["api_key"]:
                try:
                    decrypted_conn["api_key"] = decrypt_key(decrypted_conn["api_key"])
                except Exception as e:
                    logger.error(f"Error decrypting api_key for provider {provider_id}: {e}")

            base = dict(decrypted_conn)
            for k, v in cd.items():
                if v is None or v == "":
                    continue
                if k == "api_key" and v == raw_conn.get("api_key"):
                    pass  # unchanged encrypted value — keep stored decrypted value
                else:
                    base[k] = v
            cd = base

        cd.pop("masked_api_key", None)

        try:
            import os

            from langchain.chat_models import init_chat_model
            from langchain_core.messages import HumanMessage

            provider = (llm_model_provider or "").lower()

            if provider == "vllm":
                provider = "openai"
                cd["api_key"] = "EMPTY"
            elif provider == "openrouter":
                provider = "openai"
                if "base_url" not in cd:
                    cd["base_url"] = "https://openrouter.ai/api/v1"
                if "api_key" in cd:
                    cd["api_key"] = decrypt_key(cd["api_key"])
            elif "api_key" in cd and provider not in ["ollama"]:
                # Only decrypt if not already a provider_id merge (which already decrypted above)
                if not provider_id:
                    cd["api_key"] = decrypt_key(cd["api_key"])

            if provider == "openai" and (llm_model_provider or "").lower() == "openai":
                os.environ["OPENAI_API_KEY"] = cd["api_key"]
                if cd.get("organization"):
                    os.environ["OPENAI_ORG_ID"] = cd["organization"]

            model_kwargs = {
                "model_provider": provider,
                **cd,
            }

            llm = init_chat_model(**model_kwargs)
            await llm.ainvoke([HumanMessage(content="ping")])
            return {"success": True, "message": "Connection successful."}

        except Exception as e:
            logger.error(f"LLM provider test connection failed: {e}")
            return {"success": False, "message": str(e)}
