import json
import logging

import openai
from fastapi import APIRouter, WebSocket

from dependencies.auth import require_authenticated_user
from schemas.auth import AuthenticatedUser
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/audio/tts")
async def ws_tts(
    websocket: WebSocket,
    auth_user: AuthenticatedUser = require_authenticated_user(required_permissions=["create:in_progress_conversation"]),
):
    await websocket.accept()
    logger.debug("TTS WebSocket connection accepted")

    try:
        text_message = await websocket.receive_text()
        message = json.loads(text_message)["text"]

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="nova",
            response_format="mp3",
            input=message,
        ) as response:
            for chunk in response.iter_bytes(chunk_size=1024):
                await websocket.send_bytes(chunk)

        await websocket.close()
    except Exception as exc:
        logger.error(f"TTS WebSocket error: {exc}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
