import io
from typing import Any, Dict, List

import openai

from app.modules.workflow.audio.base import (
    BaseSTTProvider,
    BaseTTSProvider,
    register_stt_provider,
    register_tts_provider,
)
from app.schemas.dynamic_form_schemas.base import FieldSchema

_FORM_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="api_key",
        type="password",
        label="API Key",
        required=True,
        placeholder="sk-...",
        encrypted=True,
    ),
]


@register_tts_provider("openai")
class OpenAITTSProvider(BaseTTSProvider):
    DISPLAY_NAME = "OpenAI"
    FORM_SCHEMA = _FORM_SCHEMA
    VOICES = [
        {"value": "alloy", "label": "Alloy"},
        {"value": "echo", "label": "Echo"},
        {"value": "fable", "label": "Fable"},
        {"value": "onyx", "label": "Onyx"},
        {"value": "nova", "label": "Nova"},
        {"value": "shimmer", "label": "Shimmer"},
    ]
    MODELS = [
        {"value": "tts-1", "label": "TTS-1 (Fast)"},
        {"value": "tts-1-hd", "label": "TTS-1 HD (Quality)"},
    ]
    FORMATS = [
        {"value": "mp3", "label": "MP3"},
        {"value": "opus", "label": "Opus"},
        {"value": "aac", "label": "AAC"},
        {"value": "flac", "label": "FLAC"},
        {"value": "wav", "label": "WAV"},
        {"value": "pcm", "label": "PCM"},
    ]
    SUPPORTS_SPEED = True

    async def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        client = openai.AsyncOpenAI(api_key=self.connection_data["api_key"])
        response = await client.audio.speech.create(
            model=config.get("model", "tts-1"),
            voice=config.get("voice", "nova"),
            input=text,
            response_format=config.get("output_format", "mp3"),
            speed=float(config.get("speed", 1.0)),
        )
        return await response.aread()


@register_stt_provider("openai")
class OpenAISTTProvider(BaseSTTProvider):
    DISPLAY_NAME = "OpenAI"
    FORM_SCHEMA = _FORM_SCHEMA
    MODELS = [
        {"value": "whisper-1", "label": "Whisper-1"},
        {"value": "gpt-4o-transcribe", "label": "GPT-4o Transcribe"},
        {"value": "gpt-4o-mini-transcribe", "label": "GPT-4o Mini Transcribe"},
    ]
    RESPONSE_FORMATS = [
        {"value": "text", "label": "Plain Text"},
        {"value": "json", "label": "JSON"},
        {"value": "verbose_json", "label": "Verbose JSON"},
    ]
    SUPPORTS_TEMPERATURE = True

    async def transcribe(self, audio_bytes: bytes, audio_format: str, config: Dict[str, Any]) -> str:
        client = openai.AsyncOpenAI(api_key=self.connection_data["api_key"])
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{audio_format}"

        kwargs: Dict[str, Any] = {
            "model": config.get("model", "whisper-1"),
            "file": audio_file,
            "response_format": config.get("response_format", "text"),
            "temperature": float(config.get("temperature", 0.0)),
        }
        language = config.get("language")
        if language:
            kwargs["language"] = language

        transcript = await client.audio.transcriptions.create(**kwargs)

        if config.get("response_format", "text") == "text":
            return str(transcript)
        return transcript.model_dump() if hasattr(transcript, "model_dump") else str(transcript)
