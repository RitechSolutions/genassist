import asyncio
import audioop
import base64
import io
import json
import logging
import os
import wave

import httpx
import websockets
from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketState

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

TTS_VOICE = "alloy"
CHUNK_SIZE = 1024


async def _get_openai_session_key(
    lang_code: str = "", input_audio_format: str = "pcm16"
) -> str:
    """Get a temporary session key from OpenAI for realtime transcription."""
    url = "https://api.openai.com/v1/realtime/transcription_sessions"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    model = "gpt-4o-transcribe" if not lang_code else "whisper-1"
    if not lang_code:
        lang_code = "en"

    payload = {
        "input_audio_format": input_audio_format,
        "input_audio_transcription": {
            "model": model,
            "prompt": "",
            "language": lang_code,
        },
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 500,
        },
        "input_audio_noise_reduction": {"type": "near_field"},
        "include": ["item.input_audio_transcription.logprobs"],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["client_secret"]["value"]


async def _text_to_speech_openai(text: str) -> bytes | None:
    """Convert text to ulaw audio bytes via OpenAI TTS."""
    api_url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "tts-1",
        "input": text,
        "voice": TTS_VOICE,
        "response_format": "wav",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(api_url, headers=headers, json=data)
            response.raise_for_status()

            wav_data = response.content
            wav_io = io.BytesIO(wav_data)

            with wave.open(wav_io, "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()
                audio_data = wav_file.readframes(wav_file.getnframes())

                if sample_rate != 8000:
                    audio_data, _ = audioop.ratecv(
                        audio_data, sample_width, channels, sample_rate, 8000, None
                    )
                if channels == 2:
                    audio_data = audioop.tomono(audio_data, sample_width, 1, 1)

                return audioop.lin2ulaw(audio_data, sample_width)

        except Exception as exc:
            logger.error(f"TTS error: {exc}")
            return None


async def _process_with_agent(agent_id: str, thread_id: str, text: str) -> dict:
    """Call backend internal endpoint to process text with agent."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.BACKEND_URL}/api/internal/agents/execute",
                json={
                    "agent_id": agent_id,
                    "thread_id": thread_id,
                    "text": text,
                },
                headers={"x-internal-secret": settings.WS_INTERNAL_SECRET},
            )
            if resp.status_code != 200:
                return {"success": False, "message": "Backend agent execution failed"}
            return resp.json()
    except Exception as exc:
        logger.error(f"Agent call error: {exc}")
        return {"success": False, "message": str(exc)}


@router.websocket("/media-stream/{agent_id}")
async def handle_media_stream(
    twilio_inbound_socket: WebSocket,
    agent_id: str,
):
    """Handle Twilio media stream: bridge audio between Twilio and OpenAI."""
    logger.info(f"Media stream WebSocket connection requested for agent {agent_id}")
    await twilio_inbound_socket.accept()

    session_id: str = ""

    session_key = await _get_openai_session_key(
        lang_code="", input_audio_format="g711_ulaw"
    )

    async with websockets.connect(
        "wss://api.openai.com/v1/realtime",
        additional_headers={
            "Authorization": f"Bearer {session_key}",
            "OpenAI-Beta": "realtime=v1",
        },
    ) as transcription_ws:

        async def receive_from_twilio():
            nonlocal session_id
            try:
                async for inbound_ws_message in twilio_inbound_socket.iter_text():
                    inbound_data = json.loads(inbound_ws_message)
                    if inbound_data["event"] == "start":
                        session_id = inbound_data["start"]["streamSid"]
                        logger.info(f"Stream started. SID: {session_id}")
                    elif inbound_data["event"] == "media":
                        await transcription_ws.send(
                            json.dumps({
                                "type": "input_audio_buffer.append",
                                "audio": inbound_data["media"]["payload"],
                            })
                        )
            except Exception as exc:
                logger.error(f"Twilio receive error: {exc}")
                if transcription_ws.state == websockets.protocol.State.OPEN:
                    await transcription_ws.close()
                if twilio_inbound_socket.client_state == WebSocketState.CONNECTED:
                    await twilio_inbound_socket.close(code=1000, reason=str(exc))

        async def receive_transcription_and_respond():
            nonlocal session_id
            try:
                while (
                    twilio_inbound_socket.client_state == WebSocketState.CONNECTED
                    and transcription_ws.state == websockets.protocol.State.OPEN
                ):
                    incoming_message = await transcription_ws.recv()
                    response_data = json.loads(incoming_message)

                    if response_data.get("type") == "error":
                        raise Exception(
                            f"OpenAI error: {response_data.get('message', 'Unknown')}"
                        )

                    if (
                        response_data.get("type")
                        == "conversation.item.input_audio_transcription.completed"
                    ):
                        transcript = response_data["transcript"]
                        logger.debug(f"Transcript: '{transcript}'")

                        agent_response = await _process_with_agent(
                            agent_id, session_id, transcript
                        )

                        if not agent_response.get("success"):
                            response_text = (
                                "I'm sorry, I could not process your request. "
                                "Please try again later."
                            )
                        else:
                            response_text = str(agent_response.get("message"))

                        audio_bytes = await _text_to_speech_openai(response_text)

                        if audio_bytes and session_id:
                            for i in range(0, len(audio_bytes), CHUNK_SIZE):
                                chunk = audio_bytes[i : i + CHUNK_SIZE]
                                await twilio_inbound_socket.send_json({
                                    "event": "media",
                                    "streamSid": session_id,
                                    "media": {
                                        "payload": base64.b64encode(chunk).decode("utf-8")
                                    },
                                })

                            await twilio_inbound_socket.send_json({
                                "event": "mark",
                                "streamSid": session_id,
                                "mark": {"name": "agent_response_complete"},
                            })

                        if not agent_response.get("success"):
                            raise Exception(agent_response.get("message"))

            except Exception as exc:
                logger.error(f"Transcription/response error: {exc}")
                if transcription_ws.state == websockets.protocol.State.OPEN:
                    await transcription_ws.close()
                if twilio_inbound_socket.client_state == WebSocketState.CONNECTED:
                    await twilio_inbound_socket.close(code=1000, reason=str(exc))

        await asyncio.gather(
            receive_from_twilio(),
            receive_transcription_and_respond(),
        )
