from typing import Any, Dict, List

from google import genai
from google.genai import types

from app.modules.workflow.audio.audio_input import pcm_to_wav
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
        placeholder="AIza...",
        encrypted=True,
    ),
]

_MIME_MAP = {
    "wav": "audio/wav",
    "mp3": "audio/mp3",
    "aiff": "audio/aiff",
    "aac": "audio/aac",
    "m4a": "audio/aac",
    "ogg": "audio/ogg",
    "opus": "audio/ogg",
    "flac": "audio/flac",
    "webm": "audio/webm",
}


@register_tts_provider("gemini")
class GeminiTTSProvider(BaseTTSProvider):
    DISPLAY_NAME = "Google Gemini"
    FORM_SCHEMA = _FORM_SCHEMA
    VOICES = [
        {"value": "Kore", "label": "Kore (Firm)"},
        {"value": "Puck", "label": "Puck (Upbeat)"},
        {"value": "Zephyr", "label": "Zephyr (Bright)"},
        {"value": "Charon", "label": "Charon (Informative)"},
        {"value": "Fenrir", "label": "Fenrir (Excitable)"},
        {"value": "Leda", "label": "Leda (Youthful)"},
        {"value": "Aoede", "label": "Aoede (Breezy)"},
        {"value": "Orus", "label": "Orus (Firm)"},
    ]
    MODELS = [
        {"value": "gemini-2.5-flash-preview-tts", "label": "Gemini 2.5 Flash TTS"},
        {"value": "gemini-2.5-pro-preview-tts", "label": "Gemini 2.5 Pro TTS"},
    ]
    FORMATS = [
        {"value": "wav", "label": "WAV"},
    ]
    SUPPORTS_SPEED = False

    async def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        client = genai.Client(api_key=self.connection_data["api_key"])
        response = await client.aio.models.generate_content(
            model=config.get("model") or "gemini-2.5-flash-preview-tts",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=config.get("voice") or "Kore",
                        )
                    )
                ),
            ),
        )
        pcm = _extract_inline_audio(response)
        if not pcm:
            raise ValueError("Gemini TTS returned no audio data")
        return pcm_to_wav(pcm)


@register_stt_provider("gemini")
class GeminiSTTProvider(BaseSTTProvider):
    DISPLAY_NAME = "Google Gemini"
    FORM_SCHEMA = _FORM_SCHEMA
    MODELS = [
        {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
        {"value": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
        {"value": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
    ]
    RESPONSE_FORMATS = [
        {"value": "text", "label": "Plain Text"},
    ]
    SUPPORTS_TEMPERATURE = False

    async def transcribe(self, audio_bytes: bytes, audio_format: str, config: Dict[str, Any]) -> str:
        client = genai.Client(api_key=self.connection_data["api_key"])
        prompt = "Transcribe this audio verbatim. Return only the transcription text, nothing else."
        language = config.get("language")
        if language:
            prompt += f" The audio language is '{language}'."
        response = await client.aio.models.generate_content(
            model=config.get("model") or "gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=_MIME_MAP.get(audio_format, "audio/wav"),
                ),
                prompt,
            ],
        )
        return (response.text or "").strip()


def _extract_inline_audio(response: Any) -> bytes | None:
    """Safely pull inline audio bytes out of a generate_content response."""
    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and inline_data.data:
                return inline_data.data
    return None
