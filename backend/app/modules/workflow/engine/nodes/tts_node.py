import base64
import logging
import os
from typing import Any, Dict

import openai

from app.modules.workflow.engine.base_node import BaseNode

logger = logging.getLogger(__name__)


class TTSNode(BaseNode):
    """Text-to-Speech node using OpenAI TTS API."""

    async def process(self, config: Dict[str, Any]) -> Any:
        text = config.get("text", "")

        if not text:
            return {"error": "No text input provided for Text to Speech node"}

        model = config.get("model", "tts-1")
        voice = config.get("voice", "nova")
        output_format = config.get("output_format", "mp3")
        speed = float(config.get("speed", 1.0))

        try:
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format=output_format,
                speed=speed,
            )

            audio_bytes = await response.aread()
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

            return {
                "type": "audio",
                "format": output_format,
                "encoding": "base64",
                "data": audio_base64,
            }
        except Exception as e:
            error_msg = f"TTS generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

