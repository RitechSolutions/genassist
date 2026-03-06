import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from dependencies.auth import require_authenticated_user
from schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)

router = APIRouter()

DASHBOARD_ROOM = "DASHBOARD"


@router.websocket("/dashboard/list")
async def ws_dashboard(
    websocket: WebSocket,
    auth_user: AuthenticatedUser = require_authenticated_user(required_permissions=["*", "read:dashboard"]),
    lang: str = Query(default="en"),
    topics: list[str] = Query(default=["message"]),
):
    manager = websocket.app.state.manager
    # verifier = websocket.app.state.verifier

    # Extract tenant from query params
    tenant_id = websocket.query_params.get("x-tenant-id") or "master"

    # Connect to the dashboard room
    conn = await manager.connect(websocket, DASHBOARD_ROOM, auth_user, set(topics))

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
