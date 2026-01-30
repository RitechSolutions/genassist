import os
import json
import base64
import asyncio
from uuid import UUID
import uuid
import websockets
import httpx  # For making HTTP requests to the TTS API
import audioop  # For audio format conversion
import wave
import io
import logging

from fastapi import FastAPI, WebSocket, Request, APIRouter, Depends, Query
from fastapi_injector import Injected
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from twilio.twiml.voice_response import VoiceResponse, Connect, Say, Stream
from dotenv import load_dotenv
from app.api.v1.routes.voice import get_openai_session_key
from app.auth.dependencies import auth
from app.modules.workflow.registry import RegistryItem
from app.services.agent_config import AgentConfigService


router = APIRouter()
load_dotenv()
logger = logging.getLogger(__name__)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Missing the OpenAI API key. Please set it in the .env file.")

# Constants for audio streaming
TTS_VOICE = "alloy"
CHUNK_SIZE = 1024  # Size of audio chunks to send to Twilio


async def process_with_agent(
    agent_id: str,
    thread_id: str,
    transcribed_text: str,
    agent_service: AgentConfigService = Injected(AgentConfigService),
) -> dict:
    """
    Passes the transcribed text to your FastAPI agent endpoint using the AgentRegistry.
    """
    if not agent_id:
        error_msg = "ACTIVE_AGENT_ID is not set or passed."
        logger.error(f"AGENT ERROR: {error_msg}")
        return {
            "success": False,
            "message": "System configuration error. Agent ID is missing.",
        }

    if not thread_id:
        error_msg = "Cannot call agent without a thread_id (stream_sid)."
        logger.error(f"AGENT ERROR: {error_msg}")
        return {
            "success": False,
            "message": "I'm sorry, there was an issue with the call session.",
        }

    logger.debug(
        f"AGENT: Calling agent '{agent_id}' for thread '{thread_id}' with text: '{transcribed_text}'"
    )

    try:
        agent = await agent_service.get_by_id_full(UUID(agent_id))
        agent = RegistryItem(agent)
        agent_response = await agent.execute(
            session_message=transcribed_text, metadata={"thread_id": thread_id}
        )
        agent_response_text = agent_response.get("output")

        if not agent_response_text:
            logger.error(
                f"AGENT ERROR: Agent response was empty. Full response: {agent_response}"
            )
            return {
                "success": False,
                "message": "I received an empty response from the agent.",
            }

        logger.debug(f"AGENT: Received response from AgentRegistry: '{agent_response_text}'")
        return {"success": True, "message": agent_response_text}

    except Exception as e:
        logger.error(f"AGENT ERROR: An unexpected error occurred during agent execution: {e}")
        return {
            "success": False,
            "message": "An unexpected error has occurred with the agent. Please try again later.",
        }


async def text_to_speech_openai(text: str) -> bytes:
    """
    Alternative approach: Get WAV format from OpenAI and process it properly.
    """
    api_url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
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

            # Parse the WAV file
            wav_data = response.content
            wav_io = io.BytesIO(wav_data)

            with wave.open(wav_io, "rb") as wav_file:
                # Get audio parameters
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()

                logger.debug(
                    f"Original audio: {sample_rate}Hz, {sample_width}-byte samples, {channels} channels"
                )

                # Read all audio data
                audio_data = wav_file.readframes(wav_file.getnframes())

                # Downsample to 8kHz if needed
                if sample_rate != 8000:
                    audio_data, _ = audioop.ratecv(
                        audio_data, sample_width, channels, sample_rate, 8000, None
                    )

                # Convert to mono if stereo
                if channels == 2:
                    audio_data = audioop.tomono(audio_data, sample_width, 1, 1)

                # Convert to µ-law
                ulaw_data = audioop.lin2ulaw(audio_data, sample_width)

                return ulaw_data

        except httpx.HTTPStatusError as e:
            logger.error(
                f"TTS API request failed with status {e.response.status_code}: {e.response.text}"
            )
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during TTS processing: {e}")
            return None


@router.get("", summary="Twilio Voice API Root Endpoint", dependencies=[
    Depends(auth),
    ])
async def sample():
    return JSONResponse(
        content={
            "message": "Welcome to the Twilio Voice API. Use /incoming-call to handle incoming calls."
        },
        status_code=200,
    )


@router.get("/incoming-call/{agent_id}", summary="Handle Incoming Call", dependencies=[
    Depends(auth),
    ])
async def handle_incoming_call(request: Request, agent_id: str):
    response = VoiceResponse()
    response.say("Welcome to the Genassist!")
    response.pause(length=1)
    response.say("How can I help you?")

    host = request.url.hostname

    protocol = request.url.scheme
    ws_protocol = "wss"
    #if protocol == "http":
    #    ws_protocol = "ws"

    port = request.url.port
    if port is None:
        port = ""
    else:
        port = f":{port}"

    connect = Connect()
    connect.stream(
        url=f"{ws_protocol}://{host}{port}/api/twilio/media-stream/{agent_id}"
    )
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/media-stream/{agent_id}", dependencies=[
    Depends(auth),
    ])
async def handle_media_stream(
    twilio_inbound_socket: WebSocket,
    agent_id: str,
    agent_service: AgentConfigService = Injected(AgentConfigService),
):
    """Handle WebSocket connections for transcription and TTS playback."""
    logger.info(f"WebSocket connection requested for agent {agent_id}")
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

        async def receive_from_twilio_and_trascribe():
            nonlocal session_id
            """Receive audio from Twilio and send it to OpenAI for transcription."""
            try:
                async for inbound_ws_message in twilio_inbound_socket.iter_text():
                    inbound_data = json.loads(inbound_ws_message)
                    if inbound_data["event"] == "start":
                        session_id = inbound_data["start"]["streamSid"]
                        logger.info(
                            f"Incoming stream has started. SID/Thread ID updated to call session id: {session_id}"
                        )
                    elif inbound_data["event"] == "media":
                        await transcription_ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": inbound_data["media"]["payload"],
                                }
                            )
                        )
            except Exception as ex:
                logger.error("Twilio client disconnected.")
                logger.error(f"Error receiving from Twilio: {ex}")
                if transcription_ws.state == websockets.protocol.State.OPEN:
                    await transcription_ws.close()
                if twilio_inbound_socket.client_state == WebSocketState.CONNECTED:
                    await twilio_inbound_socket.close(code=1000, reason=str(ex))

        async def receive_twilio_transcription_and_respond():
            nonlocal session_id
            """Receive transcripts, pass to agent, and send TTS audio to Twilio."""
            try:
                while (
                    twilio_inbound_socket.client_state == WebSocketState.CONNECTED
                    and transcription_ws.state == websockets.protocol.State.OPEN
                ):
                    incoming_message = await transcription_ws.recv()
                    logger.debug(f"Received incoming message: {incoming_message}")
                    incoming_transcription_response = json.loads(incoming_message)
                    if incoming_transcription_response.get("type") == "error":
                        raise Exception(
                            f"Error in call: {incoming_transcription_response.get('message', 'Unknown error')}"
                        )

                    if (
                        incoming_transcription_response.get("type")
                        == "conversation.item.input_audio_transcription.completed"
                    ):
                        final_transcript = incoming_transcription_response["transcript"]
                        logger.debug(f"Final Transcript: '{final_transcript}'")

                        agent_response = await process_with_agent(
                            agent_id, session_id, final_transcript, agent_service
                        )
                        if not agent_response.get("success"):
                            logger.error(f"AGENT ERROR: {agent_response.get('message')}")
                            agent_response_text = "I'm sorry, I could not process your request at this time. Please try again later. Bye!"
                        else:
                            agent_response_text = str(agent_response.get("message"))

                        audio_bytes = await text_to_speech_openai(agent_response_text)

                        if audio_bytes and session_id:
                            logger.debug(
                                f"Streaming {len(audio_bytes)} bytes of TTS audio to Twilio."
                            )
                            for i in range(0, len(audio_bytes), CHUNK_SIZE):
                                chunk = audio_bytes[i : i + CHUNK_SIZE]
                                media_message = {
                                    "event": "media",
                                    "streamSid": session_id,
                                    "media": {
                                        "payload": base64.b64encode(chunk).decode(
                                            "utf-8"
                                        )
                                    },
                                }
                                await twilio_inbound_socket.send_json(media_message)

                            mark_message = {
                                "event": "mark",
                                "streamSid": session_id,
                                "mark": {"name": "agent_response_complete"},
                            }
                            await twilio_inbound_socket.send_json(mark_message)
                            logger.debug("Finished streaming TTS audio.")

                        if not agent_response.get("success"):
                            logger.error(f"AGENT ERROR: {agent_response.get('message')}")
                            raise Exception(agent_response.get("message"))

            except Exception as e:
                logger.error(f"Error in receive_from_openai_and_respond handler: {e}")
                if transcription_ws.state == websockets.protocol.State.OPEN:
                    await transcription_ws.close()
                if twilio_inbound_socket.client_state == WebSocketState.CONNECTED:
                    await twilio_inbound_socket.close(code=1000, reason=str(e))

        await asyncio.gather(
            receive_from_twilio_and_trascribe(),
            receive_twilio_transcription_and_respond(),
        )
