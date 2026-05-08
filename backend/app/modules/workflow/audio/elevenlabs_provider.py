import logging
from typing import Any, Dict, List

import httpx

from app.modules.workflow.audio.base import BaseTTSProvider, register_tts_provider
from app.schemas.dynamic_form_schemas.base import FieldSchema

logger = logging.getLogger(__name__)


@register_tts_provider("elevenlabs")
class ElevenLabsTTSProvider(BaseTTSProvider):
    DISPLAY_NAME = "ElevenLabs"
    FORM_SCHEMA: List[FieldSchema] = [
        FieldSchema(
            name="api_key",
            type="password",
            label="API Key",
            required=True,
            placeholder="Enter your ElevenLabs API key",
            encrypted=True,
        ),
    ]
    VOICES = [
        {"value": "21m00Tcm4TlvDq8ikWAM", "label": "Rachel"},
        {"value": "29vD33N1CtxCmqQRPOHJ", "label": "Drew"},
        {"value": "2EiwWnXFnvU5JabPnv8n", "label": "Clyde"},
        {"value": "5Q0t7uMcjvnagumLfvZi", "label": "Paul"},
        {"value": "AZnzlk1XvdvUeBnXmlld", "label": "Domi"},
        {"value": "EXAVITQu4vr4xnSDxMaL", "label": "Bella"},
        {"value": "ErXwobaYiN019PkySvjV", "label": "Antoni"},
        {"value": "MF3mGyEYCl7XYWbV9V6O", "label": "Elli"},
        {"value": "TxGEqnHWrfWFTfGW9XjX", "label": "Josh"},
        {"value": "VR6AewLTigWG4xSOukaG", "label": "Arnold"},
        {"value": "pNInz6obpgDQGcFmaJgB", "label": "Adam"},
        {"value": "yoZ06aMxZJJ28mfd3POQ", "label": "Sam"},
    ]
    MODELS = [
        {"value": "eleven_multilingual_v2", "label": "Multilingual v2"},
        {"value": "eleven_turbo_v2_5", "label": "Turbo v2.5"},
        {"value": "eleven_turbo_v2", "label": "Turbo v2"},
        {"value": "eleven_monolingual_v1", "label": "Monolingual v1"},
    ]
    FORMATS = [
        {"value": "mp3_44100_128", "label": "MP3 (44.1kHz, 128kbps)"},
        {"value": "mp3_22050_32", "label": "MP3 (22.05kHz, 32kbps)"},
        {"value": "pcm_16000", "label": "PCM (16kHz)"},
        {"value": "pcm_22050", "label": "PCM (22.05kHz)"},
        {"value": "pcm_24000", "label": "PCM (24kHz)"},
        {"value": "pcm_44100", "label": "PCM (44.1kHz)"},
    ]
    SUPPORTS_SPEED = False

    async def synthesize(self, text: str, config: Dict[str, Any]) -> bytes:
        api_key = self.connection_data["api_key"]
        voice_id = config.get("voice", self.VOICES[0]["value"])
        model_id = config.get("model", "eleven_multilingual_v2")
        output_format = config.get("output_format", "mp3_44100_128")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": float(config.get("stability", 0.5)),
                "similarity_boost": float(config.get("similarity_boost", 0.75)),
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url, json=payload, headers=headers, params={"output_format": output_format}
            )
            response.raise_for_status()
            return response.content
