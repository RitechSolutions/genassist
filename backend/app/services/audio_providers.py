import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi_cache.coder import PickleCoder
from fastapi_cache.decorator import cache
from injector import inject

from app.cache.redis_cache import make_key_builder
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from app.repositories.audio_providers import AudioProviderRepository
from app.schemas.audio_provider import (
    AudioProviderCreate,
    AudioProviderMinimal,
    AudioProviderRead,
    AudioProviderUpdate,
)

logger = logging.getLogger(__name__)

audio_provider_id_key_builder = make_key_builder("audio_provider_id")
audio_provider_all_key_builder = make_key_builder("-")

ENCRYPTED_FIELDS = ["api_key", "service_account_json"]


@inject
class AudioProviderService:
    def __init__(self, repository: AudioProviderRepository):
        self.repository = repository

    async def create(self, data: AudioProviderCreate):
        connection_data = data.connection_data.copy()
        connection_data = self._encrypt_fields(connection_data)
        data.connection_data = connection_data

        if data.connection_status:
            data.connection_status = data.connection_status.model_dump(mode="json")
        else:
            data.connection_status = {"status": "Untested", "last_tested_at": None, "message": None}

        return await self.repository.create(data)

    @cache(
        expire=300,
        namespace="audio_providers:get_by_id",
        key_builder=audio_provider_id_key_builder,
        coder=PickleCoder,
    )
    async def get_by_id(self, provider_id: UUID) -> AudioProviderRead:
        obj = await self.repository.get_by_id(provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        return AudioProviderRead.model_validate(obj)

    @cache(
        expire=300,
        namespace="audio_providers:get_all",
        key_builder=audio_provider_all_key_builder,
        coder=PickleCoder,
    )
    async def get_all(self) -> list[AudioProviderRead]:
        models = await self.repository.get_all()
        return [AudioProviderRead.model_validate(obj) for obj in models]

    async def get_all_by_capability(self, capability: str) -> list[AudioProviderRead]:
        all_providers = await self.get_all()
        return [
            p for p in all_providers
            if p.capability == capability or p.capability == "both"
        ]

    async def get_all_minimal(self) -> list[AudioProviderMinimal]:
        rows = await self.repository.get_all_minimal()
        return [AudioProviderMinimal.model_validate(r, from_attributes=True) for r in rows]

    async def update(self, provider_id: UUID, data: AudioProviderUpdate):
        obj = await self.repository.get_by_id(provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)

        update_data = data.model_dump(exclude_unset=True, mode="json")
        existing_conn_data = obj.connection_data or {}
        update_conn_data = update_data.get("connection_data", {})

        for field_name in ENCRYPTED_FIELDS:
            if field_name in update_conn_data:
                if not update_conn_data[field_name]:
                    del update_conn_data[field_name]
                elif (
                    field_name not in existing_conn_data
                    or update_conn_data[field_name] != existing_conn_data[field_name]
                ):
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
                fresh_test = bool(incoming_cs) and incoming_last_tested != stored_last_tested
                if fresh_test:
                    update_data["connection_status"] = incoming_cs
                else:
                    update_data["connection_status"] = {"status": "Untested", "last_tested_at": None, "message": None}
            else:
                if not update_data.get("connection_status"):
                    update_data.pop("connection_status", None)
        else:
            update_data.pop("connection_status", None)

        for field, value in update_data.items():
            setattr(obj, field, value)

        return await self.repository.update(obj)

    async def delete(self, provider_id: UUID):
        obj = await self.repository.get_by_id(provider_id)
        if not obj:
            raise AppException(error_key=ErrorKey.NOT_FOUND, status_code=404)
        await self.repository.delete(obj)
        return {"message": f"Deleted audio provider with ID {provider_id}"}

    async def test_connection(
        self,
        provider_type: Optional[str],
        capability: Optional[str],
        connection_data: Optional[Dict[str, Any]],
        provider_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        cd = dict(connection_data or {})

        if provider_id:
            decrypted = self._decrypt_fields(dict(cd))
            base = dict(decrypted)
            for k, v in cd.items():
                if v is None or v == "":
                    continue
                if k in ENCRYPTED_FIELDS and v == cd.get(k):
                    pass
                else:
                    base[k] = v
            cd = base

        try:
            from app.modules.workflow.audio import get_tts_registry, get_stt_registry

            if capability in ("tts", "both"):
                registry = get_tts_registry()
                cls = registry.get(provider_type)
                if cls:
                    provider = cls(cd)
                    await provider.synthesize("Connection test.", {"model": cls.MODELS[0]["value"], "voice": cls.VOICES[0]["value"]})
                    return {"success": True, "message": "TTS connection successful."}

            if capability in ("stt", "both"):
                registry = get_stt_registry()
                cls = registry.get(provider_type)
                if cls:
                    return {"success": True, "message": "STT provider configured (full test requires audio input)."}

            return {"success": False, "message": f"No provider found for type '{provider_type}' with capability '{capability}'."}

        except Exception as e:
            logger.error(f"Audio provider test connection failed: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def _encrypt_fields(connection_data: Dict[str, Any]) -> Dict[str, Any]:
        for field_name in ENCRYPTED_FIELDS:
            if field_name in connection_data and connection_data[field_name]:
                connection_data[field_name] = encrypt_key(connection_data[field_name])
        return connection_data

    @staticmethod
    def _decrypt_fields(connection_data: Dict[str, Any]) -> Dict[str, Any]:
        for field_name in ENCRYPTED_FIELDS:
            if field_name in connection_data and connection_data[field_name]:
                try:
                    connection_data[field_name] = decrypt_key(connection_data[field_name])
                except Exception:
                    pass
        return connection_data
