import logging
from typing import Any, Dict
from uuid import UUID

from app.core.utils.encryption_utils import decrypt_key
from app.modules.workflow.audio.base import (
    BaseSTTProvider,
    BaseTTSProvider,
    get_stt_registry,
    get_tts_registry,
)
from app.services.audio_providers import ENCRYPTED_FIELDS

logger = logging.getLogger(__name__)


async def load_connection_data(provider_id: UUID) -> tuple[str, Dict[str, Any]]:
    """Load an audio provider's type and decrypted connection data by id."""
    from app.dependencies.injector import injector
    from app.services.audio_providers import AudioProviderService

    service = injector.get(AudioProviderService)
    provider = await service.get_by_id(provider_id)
    connection_data = dict(provider.connection_data or {})
    for field in ENCRYPTED_FIELDS:
        if field in connection_data and connection_data[field]:
            connection_data[field] = decrypt_key(connection_data[field])
    return provider.provider_type, connection_data


async def get_tts_provider(provider_id: UUID) -> BaseTTSProvider:
    provider_type, connection_data = await load_connection_data(provider_id)
    registry = get_tts_registry()
    cls = registry.get(provider_type)
    if not cls:
        raise ValueError(f"Unknown TTS provider type: {provider_type}")
    return cls(connection_data)


async def get_stt_provider(provider_id: UUID) -> BaseSTTProvider:
    provider_type, connection_data = await load_connection_data(provider_id)
    registry = get_stt_registry()
    cls = registry.get(provider_type)
    if not cls:
        raise ValueError(f"Unknown STT provider type: {provider_type}")
    return cls(connection_data)


def get_all_form_schemas() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    seen = set()
    for name, cls in get_tts_registry().items():
        if name not in seen:
            result[name] = {
                "name": cls.DISPLAY_NAME,
                "display_name": cls.DISPLAY_NAME,
                "fields": cls.get_form_schema(),
            }
            seen.add(name)
    for name, cls in get_stt_registry().items():
        if name not in seen:
            result[name] = {
                "name": cls.DISPLAY_NAME,
                "display_name": cls.DISPLAY_NAME,
                "fields": cls.get_form_schema(),
            }
            seen.add(name)
    return result


def get_all_node_schemas() -> Dict[str, Any]:
    tts_schemas = {}
    for name, cls in get_tts_registry().items():
        tts_schemas[name] = cls.get_node_schema()
    stt_schemas = {}
    for name, cls in get_stt_registry().items():
        stt_schemas[name] = cls.get_node_schema()
    return {"tts": tts_schemas, "stt": stt_schemas}
