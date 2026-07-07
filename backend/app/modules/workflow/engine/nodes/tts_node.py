import logging
from typing import Any, Dict

from app.modules.workflow.audio.audio_input import build_audio_payload
from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class TTSNode(BaseNode):
    """Text-to-Speech node using configurable audio providers."""

    async def process(self, config: Dict[str, Any]) -> Any:
        text = config.get("text", "")

        if not text:
            return {"error": "No text input provided for Text to Speech node"}

        audio_provider_id = config.get("audioProviderId")
        if not audio_provider_id:
            return {"error": "No audio provider configured for Text to Speech node"}

        try:
            from app.modules.workflow.audio.provider import get_tts_provider

            provider = await get_tts_provider(audio_provider_id)
            audio_bytes = await provider.synthesize(text, config)

            return build_audio_payload(audio_bytes, config.get("output_format", "mp3"))
        except Exception as e:
            error_msg = f"TTS generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
