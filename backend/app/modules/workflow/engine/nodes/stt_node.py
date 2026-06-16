import logging
from typing import Any, Dict

from app.modules.workflow.audio.audio_input import extract_audio_input, extract_text_input
from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class STTNode(BaseNode):
    """Speech-to-Text node using configurable audio providers."""

    async def process(self, config: Dict[str, Any]) -> Any:
        audio_source = config.get("audio_source")
        if not audio_source or audio_source in ("null", "None"):
            audio_source = self.get_input_from_source()

        text_passthrough = extract_text_input(audio_source)
        if text_passthrough is not None:
            return {"message": text_passthrough}

        audio_bytes, audio_format = extract_audio_input(audio_source)

        if not audio_bytes:
            return {"error": "No audio input provided for Speech to Text node"}

        audio_provider_id = config.get("audioProviderId")
        if not audio_provider_id:
            return {"error": "No audio provider configured for Speech to Text node"}

        try:
            from app.modules.workflow.audio.provider import get_stt_provider

            provider = await get_stt_provider(audio_provider_id)
            text = await provider.transcribe(audio_bytes, audio_format, config)

            return {
                "message": text if isinstance(text, str) else str(text),
            }
        except Exception as e:
            error_msg = f"STT transcription failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
