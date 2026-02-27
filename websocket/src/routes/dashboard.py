import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from auth.token_verifier import AuthenticationError

logger = logging.getLogger(__name__)

router = APIRouter()

DASHBOARD_ROOM = "DASHBOARD"


@router.websocket("/dashboard/list")
async def ws_dashboard(
    websocket: WebSocket,
    access_token: str | None = Query(default=None),
    api_key: str | None = Query(default=None),
    lang: str = Query(default="en"),
    topics: list[str] = Query(default=["message"]),
):
    manager = websocket.app.state.manager
    verifier = websocket.app.state.verifier

    # Extract tenant from query params
    tenant_id = websocket.query_params.get("x-tenant-id") or "master"

    # Verify token ONCE
    try:
        user = await verifier.verify(
            access_token, api_key,
            ["read:in_progress_conversation"], tenant_id,
        )
    except AuthenticationError as exc:
        await websocket.close(code=4401, reason=exc.detail)
        return

    conn = await manager.connect(websocket, DASHBOARD_ROOM, user, set(topics))

    try:
        while True:
            data = await websocket.receive_text()
            conn.last_pong = time.time()
    except WebSocketDisconnect:
        logger.debug(f"Dashboard WebSocket disconnected: tenant={tenant_id}")
        await manager.disconnect(websocket, DASHBOARD_ROOM, tenant_id)
    except Exception as exc:
        logger.exception(f"Unexpected dashboard WebSocket error: {exc}")
        await manager.disconnect(websocket, DASHBOARD_ROOM, tenant_id)
