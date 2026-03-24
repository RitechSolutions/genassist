import asyncio
import base64
import json
import logging
import os

import websockets
from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketState

from config import settings
from services.twillio import (
    get_openai_session_key,
    process_with_agent,
    text_to_speech_openai,
)

logger = logging.getLogger(__name__)

router = APIRouter()

CHUNK_SIZE = 1024


@router.websocket("/media-stream/{agent_id}")
async def handle_media_stream(
    twilio_inbound_socket: WebSocket,
    agent_id: str,
):
    """Handle Twilio media stream: bridge audio between Twilio and OpenAI."""
    logger.info(f"Media stream WebSocket connection requested for agent {agent_id}")
    await twilio_inbound_socket.accept()

    session_id: str = ""

    session_key = await get_openai_session_key(
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

                        agent_response = await process_with_agent(
                            agent_id, session_id, transcript
                        )

                        if not agent_response.get("success"):
                            response_text = (
                                "I'm sorry, I could not process your request. "
                                "Please try again later."
                            )
                        else:
                            response_text = str(agent_response.get("message"))

                        audio_bytes = await text_to_speech_openai(response_text)

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
