import asyncio
from datetime import datetime, timezone
from uuid import UUID

from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.websockets.socket_room_enum import SocketRoomType

SYSTEM_USER_ID = UUID(int=0)


def transcript_conversation_notification_url(conversation_id: UUID | str) -> str:
    """Deep link to Transcripts: opens ActiveConversationDialog if live, else TranscriptDialog."""
    return f"/transcripts?conversation={conversation_id}"


def notification_payload(
    *,
    notification_id: str,
    title: str,
    description: str,
    level: str,
    action_url: str,
    timestamp: datetime | None = None,
) -> dict:
    return {
        "id": notification_id,
        "title": title,
        "description": description,
        "type": level,
        "action_url": action_url,
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
    }


def emit_notification(
    *,
    socket_connection_manager: SocketConnectionManager,
    tenant_id: str | None,
    payload: dict,
    current_user_id: UUID | None = None,
) -> None:
    _ = asyncio.create_task(
        socket_connection_manager.broadcast(
            msg_type="notification",
            payload=payload,
            room_id=SocketRoomType.DASHBOARD,
            current_user_id=current_user_id or SYSTEM_USER_ID,
            required_topic="notification",
            tenant_id=tenant_id,
        )
    )
