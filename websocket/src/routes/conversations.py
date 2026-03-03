import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from dependencies.auth import require_authenticated_user
from schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/conversations/{conversation_id}")
async def ws_conversation(
    websocket: WebSocket,
    conversation_id: str,
    auth_user: AuthenticatedUser = require_authenticated_user(required_permissions=["update:in_progress_conversation"]),
    lang: str = Query(default="en"),
    topics: list[str] = Query(default=["message"]),
):
    manager = websocket.app.state.manager
    publisher = websocket.app.state.publisher

    # Extract tenant from query params
    tenant_id = websocket.query_params.get("x-tenant-id") or "master"

    conn = await manager.connect(websocket, conversation_id, auth_user, set(topics))

    try:
        while True:
            data = await websocket.receive_text()
            # Update last_pong on any received message (including pong)
            conn.last_pong = time.time()
            # Optionally publish upstream for backend processing
            if data and publisher:
                await publisher.publish_upstream(
                    tenant_id, conversation_id, auth_user.user_id, data,
                )
    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected: conversation={conversation_id} tenant={tenant_id}")
        await manager.disconnect(websocket, conversation_id, tenant_id)
    except Exception as exc:
        logger.exception(f"Unexpected WebSocket error: {exc}")
        await manager.disconnect(websocket, conversation_id, tenant_id)
