from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Hashable

from fastapi import WebSocket

from auth.models import AuthenticatedUser
from connections.models import Connection

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket rooms with multi-tenant isolation.
    Connections are stored in-memory per room (tenant_id:room_id).
    """

    def __init__(self):
        self._rooms: dict[str, list[Connection]] = {}
        self._lock = asyncio.Lock()

    def _tenant_aware_room_id(self, room_id: Hashable, tenant_id: str | None) -> str:
        if tenant_id:
            return f"{tenant_id}:{room_id}"
        return str(room_id)

    async def connect(
        self,
        websocket: WebSocket,
        room_id: Hashable,
        user: AuthenticatedUser,
        topics: set[str],
    ) -> Connection:
        await websocket.accept()
        now = time.time()
        conn = Connection(
            websocket=websocket,
            user_id=user.user_id,
            permissions=user.permissions,
            tenant_id=user.tenant_id,
            topics=topics,
            connected_at=now,
            last_pong=now,
        )
        ta_room = self._tenant_aware_room_id(room_id, user.tenant_id)
        async with self._lock:
            self._rooms.setdefault(ta_room, []).append(conn)
            logger.info(
                f"[CONNECT] room={ta_room} user={user.user_id} topics={topics} "
                f"total_in_room={len(self._rooms[ta_room])}"
            )
        return conn

    async def disconnect(
        self,
        websocket: WebSocket,
        room_id: Hashable | None = None,
        tenant_id: str | None = None,
    ) -> None:
        async with self._lock:
            if room_id is not None:
                ta_room = self._tenant_aware_room_id(room_id, tenant_id)
                conns = self._rooms.get(ta_room, [])
                self._rooms[ta_room] = [c for c in conns if c.websocket is not websocket]
                if not self._rooms[ta_room]:
                    del self._rooms[ta_room]
                    logger.debug(f"Room {ta_room} removed (empty)")
            else:
                # Search all rooms
                to_remove = []
                for key, conns in self._rooms.items():
                    filtered = [c for c in conns if c.websocket is not websocket]
                    if len(filtered) < len(conns):
                        if filtered:
                            self._rooms[key] = filtered
                        else:
                            to_remove.append(key)
                for key in to_remove:
                    del self._rooms[key]
                    logger.debug(f"Room {key} removed (empty)")

    async def broadcast_to_room(
        self,
        tenant_aware_room_id: str,
        msg_type: str,
        payload: dict,
        required_topic: str | None = None,
    ) -> None:
        message = json.dumps({"type": msg_type, "payload": payload}, default=str)
        targets = list(self._rooms.get(tenant_aware_room_id, []))

        if not targets:
            return

        logger.debug(
            f"[BROADCAST] room={tenant_aware_room_id} targets={len(targets)} "
            f"type={msg_type} topic={required_topic}"
        )

        for conn in targets:
            if required_topic and required_topic not in conn.topics:
                continue
            try:
                await conn.websocket.send_text(message)
            except Exception as exc:
                logger.warning(f"[BROADCAST] Failed to send to user {conn.user_id}: {exc}")
                await self.disconnect(conn.websocket)

    def get_stats(self) -> dict:
        total = 0
        by_tenant: dict[str, int] = {}
        for conns in self._rooms.values():
            for conn in conns:
                total += 1
                by_tenant[conn.tenant_id] = by_tenant.get(conn.tenant_id, 0) + 1
        return {
            "total_connections": total,
            "rooms_count": len(self._rooms),
            "connections_by_tenant": by_tenant,
        }

    @property
    def rooms(self) -> dict[str, list[Connection]]:
        return self._rooms
