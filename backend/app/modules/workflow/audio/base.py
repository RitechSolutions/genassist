from abc import ABC, abstractmethod
from typing import Any, ClassVar, Dict, List, Type

from app.schemas.dynamic_form_schemas.base import FieldSchema


_tts_registry: Dict[str, Type["BaseTTSProvider"]] = {}
_stt_registry: Dict[str, Type["BaseSTTProvider"]] = {}


def register_tts_provider(name: str):
    def decorator(cls: Type["BaseTTSProvider"]):
        _tts_registry[name] = cls
        return cls
    return decorator


def register_stt_provider(name: str):
    def decorator(cls: Type["BaseSTTProvider"]):
        _stt_registry[name] = cls
        return cls
    return decorator


def get_tts_registry() -> Dict[str, Type["BaseTTSProvider"]]:
    return dict(_tts_registry)


def get_stt_registry() -> Dict[str, Type["BaseSTTProvider"]]:
    return dict(_stt_registry)


class BaseTTSProvider(ABC):
    DISPLAY_NAME: ClassVar[str]
    FORM_SCHEMA: ClassVar[List[FieldSchema]]
    VOICES: ClassVar[List[Dict[str, str]]]
    MODELS: ClassVar[List[Dict[str, str]]]
    FORMATS: ClassVar[List[Dict[str, str]]]
    SUPPORTS_SPEED: ClassVar[bool] = True

    def __init__(self, connection_data: Dict[str, Any]):
        self.connection_data = connection_data

    @abstractmethod
    async def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        ...

    @classmethod
    def get_node_schema(cls) -> Dict[str, Any]:
        return {
            "display_name": cls.DISPLAY_NAME,
            "voices": cls.VOICES,
            "models": cls.MODELS,
            "formats": cls.FORMATS,
            "supports_speed": cls.SUPPORTS_SPEED,
        }

    @classmethod
    def get_form_schema(cls) -> List[Dict[str, Any]]:
        return [f.model_dump(exclude_none=True) for f in cls.FORM_SCHEMA]


class BaseSTTProvider(ABC):
    DISPLAY_NAME: ClassVar[str]
    FORM_SCHEMA: ClassVar[List[FieldSchema]]
    MODELS: ClassVar[List[Dict[str, str]]]
    RESPONSE_FORMATS: ClassVar[List[Dict[str, str]]]
    SUPPORTS_TEMPERATURE: ClassVar[bool] = True

    def __init__(self, connection_data: Dict[str, Any]):
        self.connection_data = connection_data

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, audio_format: str, config: Dict[str, Any]) -> str:
        ...

    @classmethod
    def get_node_schema(cls) -> Dict[str, Any]:
        return {
            "display_name": cls.DISPLAY_NAME,
            "models": cls.MODELS,
            "response_formats": cls.RESPONSE_FORMATS,
            "supports_temperature": cls.SUPPORTS_TEMPERATURE,
        }

    @classmethod
    def get_form_schema(cls) -> List[Dict[str, Any]]:
        return [f.model_dump(exclude_none=True) for f in cls.FORM_SCHEMA]
