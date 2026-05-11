import base64
import json
import logging
from typing import Any, Dict

from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class STTNode(BaseNode):
    """Speech-to-Text node using configurable audio providers."""

    async def process(self, config: Dict[str, Any]) -> Any:
        audio_source = config.get("audio_source")
        if not audio_source or audio_source in ("null", "None"):
            audio_source = self.get_input_from_source()

        audio_bytes, audio_format = self._extract_audio(audio_source)

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

    def _extract_audio(self, source_output: Any) -> tuple[bytes | None, str]:
        if isinstance(source_output, dict):
            if source_output.get("type") == "audio" and source_output.get("data"):
                encoding = source_output.get("encoding", "base64")
                audio_format = source_output.get("format", "mp3")
                if encoding == "base64":
                    audio_bytes = base64.b64decode(source_output["data"])
                    if len(audio_bytes) > 100:
                        return audio_bytes, audio_format
                    logger.warning("Decoded audio data too small (%d bytes), likely invalid", len(audio_bytes))
                    return None, audio_format
            if "audio_data" in source_output:
                return self._extract_audio(source_output["audio_data"])

        if isinstance(source_output, str) and source_output:
            try:
                parsed = json.loads(source_output)
                if isinstance(parsed, dict):
                    return self._extract_audio(parsed)
            except (json.JSONDecodeError, ValueError):
                pass
            try:
                audio_bytes = base64.b64decode(source_output)
                if len(audio_bytes) > 100:
                    return audio_bytes, "mp3"
                logger.warning("Decoded audio data too small (%d bytes), likely invalid", len(audio_bytes))
            except Exception:
                logger.warning("audio_source string is not valid base64")

        return None, "mp3"
