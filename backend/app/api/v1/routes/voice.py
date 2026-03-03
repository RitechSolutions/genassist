import json
import logging
import os
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from app.auth.dependencies import auth, permissions
from app.core.permissions.constants import Permissions as P

from app.tasks.audio_tasks import transcribe_audio_files_async

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/openai/session", summary="Get a temporary session key for OpenAI API",
            dependencies=[
                Depends(auth),
                Depends(permissions(P.Conversation.CREATE_IN_PROGRESS))
            ])
async def get_openai_session_key(lang_code: str = Query(default=""), input_audio_format: str = Query(default="pcm16")) -> str:
    """
    Get a temporary session key for OpenAI API.
    This endpoint is used to create a session key for the OpenAI API."""

    url = "https://api.openai.com/v1/realtime/transcription_sessions"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "Content-Type": "application/json",
    }

    #"model": "whisper-1" | "gpt-4o-transcribe" | "gpt-4o-mini-transcribe",
    # "gpt-4o-transcribe" for multilingual transcription
    # whisper-1 for single language transcription

    #input_audio_format: pcm16 | g711_ulaw
    model = "gpt-4o-transcribe"  # Default model for multilingual transcription
    if lang_code:
        model = "whisper-1"  # Use whisper-1 for single language transcription
    else:
        lang_code = "en"  # Default to English if no language code is provided
          
    payload = {
                "input_audio_format": input_audio_format,
                "input_audio_transcription": {
                    "model": model,
                    "prompt": "",
                    "language": lang_code
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "input_audio_noise_reduction": {
                    "type": "near_field"
                },
                "include": [
                    "item.input_audio_transcription.logprobs"
                ]
            }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return data["client_secret"]["value"]


# TTS WebSocket endpoint has been moved to the standalone websocket service.


@router.get("/run-s3-audio-sync/{item_id}", status_code=200, summary="Trabscribe the content of S3 Bucket  defined Datasource", dependencies=[Depends(auth)])
async def s3_audio_transcribe(
    item_id: Optional[str] = None,
):
    try:
        return await transcribe_audio_files_async(item_id)
    except Exception as e:
        logger.error(f"Error in handler: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")