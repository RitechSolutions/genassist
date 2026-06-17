"""
Live voice conversation endpoint (backend-held session).

The browser opens this WebSocket directly; the backend holds the Gemini Live
session for the audio. Each completed turn is persisted through the SAME
`process_conversation_update_with_agent` flow that powers normal/record-send chat
(transcript, broadcast, dashboard, tone, agent log, memory, side-effect nodes) —
the Voice Agent node short-circuits to the already-produced reply, so there's no
second Gemini call.
"""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from fastapi_injector import Injected

from app.auth.dependencies import socket_auth
from app.modules.workflow.agents.live_agent_gemini import GeminiLiveAgent
from app.schemas.conversation_transcript import InProgConvTranscrUpdate, TranscriptSegmentInput
from app.schemas.socket_principal import SocketPrincipal
from app.services.agent_config import AgentConfigService

router = APIRouter()
logger = logging.getLogger(__name__)


async def _recv_from_client(websocket: WebSocket, audio_in: asyncio.Queue) -> None:
    """Pump inbound binary mic frames into the audio queue until disconnect."""
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                await audio_in.put(message["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        await audio_in.put(None)


@router.websocket("/live/{agent_id}")
async def ws_live_voice(
    websocket: WebSocket,
    agent_id: str,
    thread_id: str = Query(...),
    principal: SocketPrincipal = socket_auth(["update:in_progress_conversation"]),
    agent_service: AgentConfigService = Injected(AgentConfigService),
):
    """Hold a live voice conversation against an agent's Voice Agent node."""
    tenant_id = getattr(principal, "tenant_id", None) or "master"

    # Resolve the node + its live config BEFORE accepting, so we can reject cleanly.
    try:
        from app.modules.workflow.engine.nodes.voice_agent_node import VoiceAgentNode

        node = await VoiceAgentNode.materialize(agent_service, agent_id, thread_id)
        cfg = await node.build_live_session_config()
    except Exception as exc:
        logger.warning("Live voice setup failed for agent %s: %s", agent_id, exc)
        await websocket.close(code=4404)
        return

    try:  # the SDK must be installed
        from google import genai  # noqa: F401
    except ImportError:
        logger.error("google-genai not installed")
        await websocket.close(code=4500)
        return

    async def _set_transcript(transcript: str) -> None:
        # The agent runs the tools itself; the node only contributes the engine
        # state piece — exposing the live transcript to `{{session.message}}`.
        node.set_live_transcript(transcript)

    # Per completed turn: route through the SAME flow as normal/record-send chat.
    # The injected `live_result` makes VoiceAgentNode.process() short-circuit to the
    # already-spoken reply (no second Gemini call / no double tools), so we reuse
    # transcript persistence, broadcast, dashboard, tone, agent log, memory, and the
    # full DAG (side-effect nodes) for free. Runs in the session's background persist
    # task, so it never blocks the next spoken turn.
    async def _persist(user_text: str, agent_text: str, steps: list) -> None:
        # Persistence reuses the normal conversation-update flow, which requires an
        # existing in-progress conversation keyed by a UUID. A non-UUID thread_id
        # (e.g. the client's pre-conversation fallback) can't map to one, so skip
        # with a clear warning instead of letting UUID() raise per turn.
        try:
            conversation_uuid = UUID(thread_id)
        except ValueError:
            logger.warning(
                "Live voice: thread_id %r is not a conversation UUID; "
                "transcript persistence skipped for this call.",
                thread_id,
            )
            return

        # Lazy import to avoid a route-load import cycle (the use case imports
        # from routes.agents).
        from app.use_cases.chat_as_client_use_case import (
            process_conversation_update_with_agent,
        )

        model = InProgConvTranscrUpdate(
            messages=[
                TranscriptSegmentInput(
                    start_time=0.0,
                    end_time=0.0,
                    speaker="customer",
                    text=user_text or "[Voice message]",
                    type="message",
                )
            ],
            metadata={
                "live_result": {
                    "message": agent_text,
                    "transcript": user_text,
                    "steps": steps,
                }
            },
        )
        await process_conversation_update_with_agent(
            conversation_id=conversation_uuid,
            model=model,
            tenant_id=tenant_id,
            current_user_id=UUID(str(principal.user_id)),
            audio_bytes=None,
            audio_format=None,
        )

    # The agent executes the node's (PII-wrapped) tools itself; `_set_transcript`
    # only feeds the live transcript into the workflow state for `{{session.message}}`.
    agent = GeminiLiveAgent(
        api_key=cfg["api_key"],
        model=cfg.get("model"),
        live_config=cfg["live_config"],
        tools=cfg["tools"],
        max_tool_calls=int(cfg.get("max_tool_calls", 10)),
        on_transcript=_set_transcript,
        persist_turn=_persist,
    )

    await websocket.accept()
    logger.info("Live voice accepted: agent=%s thread=%s user=%s", agent_id, thread_id, principal.user_id)

    audio_in: asyncio.Queue = asyncio.Queue()
    recv_task = asyncio.create_task(_recv_from_client(websocket, audio_in))
    agent_task = asyncio.create_task(
        agent.stream(audio_in, websocket.send_bytes, websocket.send_json)
    )
    try:
        _, pending = await asyncio.wait(
            {recv_task, agent_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if agent_task.done() and not agent_task.cancelled():
            exc = agent_task.exception()
            if exc and websocket.client_state == WebSocketState.CONNECTED:
                logger.exception("Live voice session error", exc_info=exc)
                await websocket.send_json({"type": "error", "message": str(exc)})
    except Exception:
        logger.exception("Live voice handler error")
    finally:
        recv_task.cancel()
        agent_task.cancel()
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
