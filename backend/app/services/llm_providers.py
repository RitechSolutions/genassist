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
from app.schemas.llm import LlmProviderCreate, LlmProviderMinimal, LlmProviderRead, LlmProviderUpdate

logger = logging.getLogger(__name__)

llm_provider_id_key_builder = make_key_builder("llm_provider_id")
llm_provider_all_key_builder = make_key_builder("-")


@inject
class LlmProviderService:
    encrypted_fields = [
        "api_key",
        "aws_access_key_id",
        "aws_secret_access_key",
    ]

    def __init__(self, repository: LlmProviderRepository):
        self.repository = repository

    async def create(self, data: LlmProviderCreate):
        connection_data = data.connection_data.copy()

        api_key = connection_data.get("api_key")
        if api_key:
            connection_data["masked_api_key"] = get_masked_api_key(api_key)

        connection_data = await self.encrypt_connection_data_fields(connection_data)
        data.connection_data = connection_data

        if data.connection_status:
            data.connection_status = data.connection_status.model_dump(mode="json")
        else:
            data.connection_status = {"status": "Untested", "last_tested_at": None, "message": None}

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

    async def get_all_minimal(self) -> list[LlmProviderMinimal]:
        rows = await self.repository.get_all_minimal()
        return [LlmProviderMinimal.model_validate(r, from_attributes=True) for r in rows]

    async def update(self, llm_provider_id: UUID, data: LlmProviderUpdate):
        obj = await self.repository.get_by_id(llm_provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.LLM_PROVIDER_NOT_FOUND, status_code=404)

        update_data = data.model_dump(exclude_unset=True, mode="json")

        existing_conn_data = obj.connection_data or {}
        update_conn_data = update_data.get("connection_data", {})

        for field_name in self.encrypted_fields:
            if field_name in update_conn_data:
                if update_conn_data[field_name] == "" or update_conn_data[field_name] is None:
                    del update_conn_data[field_name]
                elif (
                    field_name not in existing_conn_data
                    or update_conn_data[field_name] != existing_conn_data[field_name]
                ):
                    if field_name == "api_key":
                        update_conn_data["masked_api_key"] = get_masked_api_key(update_conn_data[field_name])
                    update_conn_data[field_name] = encrypt_key(update_conn_data[field_name])

        if "connection_data" in update_data:
            connection_data_changed = any(
                update_data["connection_data"].get(k) != existing_conn_data.get(k)
                for k in update_data["connection_data"]
            )

            if connection_data_changed:
                incoming_cs = update_data.get("connection_status")
                stored_cs = obj.connection_status or {}
                stored_last_tested = stored_cs.get("last_tested_at")

                incoming_last_tested = None
                if isinstance(incoming_cs, dict):
                    incoming_last_tested = incoming_cs.get("last_tested_at")
                elif hasattr(incoming_cs, "last_tested_at"):
                    incoming_last_tested = getattr(incoming_cs, "last_tested_at", None)

                fresh_test = bool(incoming_cs) and incoming_last_tested != stored_last_tested

                if fresh_test:
                    update_data["connection_status"] = incoming_cs
                else:
                    update_data["connection_status"] = {"status": "Untested", "last_tested_at": None, "message": None}
            else:
                # connection_data unchanged — preserve provided connection_status (e.g., test result)
                if not update_data.get("connection_status"):
                    update_data.pop("connection_status", None)
        else:
            update_data.pop("connection_status", None)

        for field, value in update_data.items():
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
            # stored_raw = await self.repository.get_by_id(provider_id)
            # raw_conn = dict((stored_raw.connection_data if stored_raw else None) or {})
            # decrypted_conn = await self.decrypt_connection_data_fields(dict(raw_conn), provider_id)
            decrypted_conn = await self.decrypt_connection_data_fields(cd)

            base = dict(decrypted_conn)
            for k, v in cd.items():
                if v is None or v == "":
                    continue
                if k in self.encrypted_fields and v == cd.get(k):
                    pass  # unchanged encrypted field — keep stored decrypted value
                else:
                    base[k] = v  # new plaintext value from user
            cd = base

        cd.pop("masked_api_key", None)

        try:
            from langchain_core.messages import HumanMessage

            from app.modules.workflow.llm.provider import build_chat_model

            llm = await build_chat_model(
                provider_name=llm_model_provider,
                connection_data=cd,
                model_name=cd.get("model"),
            )
            await llm.ainvoke([HumanMessage(content="ping")])
            return {"success": True, "message": "Connection successful."}

        except Exception as e:
            logger.error(f"LLM provider test connection failed: {e}")
            return {"success": False, "message": str(e)}

    async def encrypt_connection_data_fields(
        self, connection_data: Dict[str, Any], provider_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        for field_name in self.encrypted_fields:
            if field_name in connection_data and connection_data[field_name]:
                try:
                    connection_data[field_name] = encrypt_key(connection_data[field_name])
                except Exception as e:
                    logger.error(
                        f"Error encrypting field '{field_name}' for provider ID '{provider_id}': {e}"
                    )
        return connection_data

    async def decrypt_connection_data_fields(
        self, connection_data: Dict[str, Any], provider_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        for field_name in self.encrypted_fields:
            if field_name in connection_data and connection_data[field_name]:
                try:
                    connection_data[field_name] = decrypt_key(connection_data[field_name])
                except Exception as e:
                    logger.error(
                        f"Error decrypting field '{field_name}' for provider ID '{provider_id}': {e}"
                    )
        return connection_data
