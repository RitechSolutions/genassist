from __future__ import annotations

import json
import logging
from typing import Hashable
from uuid import UUID

from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class SocketConnectionManager:
    """
    Redis-publish-only broadcaster. WebSocket connections are now managed by the
    standalone websocket. This class only publishes messages to Redis
    Pub/Sub channels for delivery by the websocket.
    """

    def __init__(self, redis_client=None) -> None:
        self._redis_client = redis_client

    def _get_tenant_aware_room_id(self, room_id: Hashable, tenant_id: str | None) -> Hashable:
        if tenant_id:
            return f"{tenant_id}:{room_id}"
        return room_id

    def _get_redis_channel(self, tenant_aware_room_id: Hashable) -> str:
        return f"websocket:{tenant_aware_room_id}"

    async def broadcast(
        self,
        room_id: Hashable,
        msg_type: str,
        current_user_id: UUID,
        payload: dict | None = None,
        required_topic: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """
        Publish a message to Redis Pub/Sub for delivery by the websocket.
        """
        if not settings.USE_WS:
            return

        payload = payload or {}
        if msg_type == "takeover":
            payload["takeover_user_id"] = str(current_user_id)

        tenant_aware_room_id = self._get_tenant_aware_room_id(room_id, tenant_id)

        if not self._redis_client:
            logger.warning("[BROADCAST] Redis not configured, message dropped")
            return

        try:
            redis_channel = self._get_redis_channel(tenant_aware_room_id)
            message_data = {
                "type": msg_type,
                "payload": payload,
                "required_topic": required_topic,
                "room_id": str(room_id),
                "tenant_id": tenant_id,
            }
            await self._redis_client.publish(
                redis_channel,
                json.dumps(message_data, default=str),
            )
            logger.info(
                f"[BROADCAST] Published to Redis channel: {redis_channel} | "
                f"Type: {msg_type} | Topic: {required_topic}"
            )
        except Exception as exc:
            logger.error(f"[BROADCAST] Failed to publish to Redis: {exc}")
