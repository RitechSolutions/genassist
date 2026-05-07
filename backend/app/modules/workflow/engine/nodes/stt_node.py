import base64
import io
import logging
import os
from typing import Any, Dict

import openai

from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class STTNode(BaseNode):
    """Speech-to-Text node using OpenAI Whisper API."""

    async def process(self, config: Dict[str, Any]) -> Any:
        audio_source = config.get("audio_source")
        if not audio_source:
            audio_source = self.get_input_from_source()

        audio_bytes, audio_format = self._extract_audio(audio_source)

        if not audio_bytes:
            return {"error": "No audio input provided for Speech to Text node"}

        model = config.get("model", "whisper-1")
        language = config.get("language") or None
        response_format = config.get("response_format", "text")
        temperature = float(config.get("temperature", 0.0))

        try:
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = f"audio.{audio_format}"

            kwargs: Dict[str, Any] = {
                "model": model,
                "file": audio_file,
                "response_format": response_format,
                "temperature": temperature,
            }
            if language:
                kwargs["language"] = language

            transcript = await client.audio.transcriptions.create(**kwargs)

            if response_format == "text":
                text = str(transcript)
            else:
                text = transcript.model_dump() if hasattr(transcript, "model_dump") else transcript

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
                    return base64.b64decode(source_output["data"]), audio_format

        if isinstance(source_output, str) and source_output:
            try:
                return base64.b64decode(source_output), "mp3"
            except Exception:
                logger.warning("audio_source string is not valid base64")

        return None, "mp3"
