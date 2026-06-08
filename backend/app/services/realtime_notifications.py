import asyncio
from datetime import datetime, timezone
import logging
from uuid import UUID

from app.core.tenant_scope import clear_tenant_context, set_tenant_context
from app.db.multi_tenant_session import multi_tenant_manager
from app.modules.websockets.socket_connection_manager import SocketConnectionManager
from app.modules.websockets.socket_room_enum import SocketRoomType
from app.repositories.notification import NotificationRepository, PersistedNotificationRepository
from app.services.notification_orchestrator import NotificationOrchestratorService

SYSTEM_USER_ID = UUID(int=0)
logger = logging.getLogger(__name__)


def transcript_conversation_notification_url(conversation_id: UUID | str) -> str:
    """Deep link to Transcripts: opens ActiveConversationDialog if live, else TranscriptDialog."""
    return f"/transcripts?conversation={conversation_id}"


def conversation_short_id(conversation_id: UUID | str) -> str:
    return f"#{str(conversation_id).replace('-', '')[-4:]}"


def conversation_started_notification_description(conversation_id: UUID | str) -> str:
    return f"A new conversation has started {conversation_short_id(conversation_id)}."


def notification_payload(
    *,
    notification_id: str,
    title: str,
    description: str,
    level: str,
    action_url: str,
    timestamp: datetime | None = None,
    group_id: UUID | str | None = None,
    type_key: str | None = None,
    entity_kind: str | None = None,
    entity_id: UUID | str | None = None,
    event_key: str | None = None,
    metadata: dict | None = None,
) -> dict:
    resolved_type_key = type_key or str(notification_id).split(":", 1)[0]
    payload = {
        "id": notification_id,
        "type_key": resolved_type_key,
        "title": title,
        "description": description,
        "type": level,
        "action_url": action_url,
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
    }
    if group_id is not None:
        payload["group_id"] = str(group_id)
    if entity_kind is not None:
        payload["entity_kind"] = entity_kind
    if entity_id is not None:
        payload["entity_id"] = str(entity_id)
    if event_key is not None:
        payload["event_key"] = event_key
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


def emit_notification(
    *,
    socket_connection_manager: SocketConnectionManager,
    tenant_id: str | None,
    payload: dict,
    current_user_id: UUID | None = None,
) -> None:
    async def _persist_notification_payload() -> dict:
        type_key = str(payload.get("type_key") or "").strip()
        if not type_key:
            return payload

        session = None
        try:
            if tenant_id:
                set_tenant_context(tenant_id)
            session_factory = multi_tenant_manager.get_tenant_session_factory(tenant_id)
            session = session_factory()

            notification_repo = NotificationRepository(session)
            persisted_repo = PersistedNotificationRepository(session)
            orchestrator = NotificationOrchestratorService(
                notification_repository=notification_repo,
                persisted_notification_repository=persisted_repo,
            )

            persisted_payload = await orchestrator.persist_notification_event(
                type_key=type_key,
                level=str(payload.get("type") or "info"),
                title=str(payload.get("title") or ""),
                description=str(payload.get("description") or ""),
                action_url=str(payload.get("action_url") or "/"),
                entity_kind=payload.get("entity_kind"),
                entity_id=UUID(str(payload.get("entity_id"))) if payload.get("entity_id") else None,
                event_key=payload.get("event_key"),
                metadata=payload.get("metadata"),
                group_id=UUID(str(payload.get("group_id"))) if payload.get("group_id") else None,
            )
            return persisted_payload or payload
        except Exception:
            logger.warning("Persisted notification creation failed; broadcasting fallback payload", exc_info=True)
            return payload
        finally:
            if session is not None:
                await session.close()
            if tenant_id:
                clear_tenant_context()

    async def _persist_and_broadcast() -> None:
        out_payload = await _persist_notification_payload()

        await socket_connection_manager.broadcast(
            msg_type="notification",
            payload=out_payload,
            room_id=SocketRoomType.DASHBOARD,
            current_user_id=current_user_id or SYSTEM_USER_ID,
            required_topic="notification",
            tenant_id=tenant_id,
        )

    _ = asyncio.create_task(_persist_and_broadcast())
