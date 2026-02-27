import logging

from fastapi import Request, APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from twilio.twiml.voice_response import VoiceResponse, Connect
from app.auth.dependencies import auth


router = APIRouter()
logger = logging.getLogger(__name__)


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

    ws_protocol = "wss"

    port = request.url.port
    if port is None:
        port = ""
    else:
        port = f":{port}"

    connect = Connect()
    # Media-stream is now handled by the standalone websocket service
    connect.stream(
        url=f"{ws_protocol}://{host}:8002/ws/media-stream/{agent_id}"
    )
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


# Media-stream WebSocket endpoint has been moved to the standalone websocket service.
