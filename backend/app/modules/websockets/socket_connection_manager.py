from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Hashable, List, Sequence, Set
from uuid import UUID
from fastapi.websockets import WebSocket

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Connection:
    websocket: WebSocket
    user_id: UUID
    permissions: Sequence[str]
    tenant_id: str | None  # Tenant identifier for multi-tenant isolation
    topics: Set[str] = field(default_factory=set)


class SocketConnectionManager:
    """
    Global singleton for managing WebSocket rooms.
    """

    def __init__(self) -> None:
        self._rooms: Dict[Hashable, List[Connection]] = {}
        self._lock = asyncio.Lock()

    def _get_tenant_aware_room_id(
        self, room_id: Hashable, tenant_id: str | None
    ) -> Hashable:
        """
        Create a tenant-aware room ID for proper multi-tenant isolation.
        """
        if tenant_id:
            return f"{tenant_id}:{room_id}"
        return room_id

    # ------------ lifecycle -------------------------------------------------

    async def connect(
        self,
        websocket: WebSocket,
        room_id: Hashable,
        user_id: UUID,
        permissions: Sequence[str],
        tenant_id: str | None = None,
        topics: Sequence[str] | None = None,
    ) -> None:
        await websocket.accept()
        topics = topics or ()

        # Create tenant-aware room ID
        tenant_aware_room_id = self._get_tenant_aware_room_id(room_id, tenant_id)

        async with self._lock:
            self._rooms.setdefault(tenant_aware_room_id, []).append(
                Connection(websocket, user_id, permissions, tenant_id, set(topics))
            )
            logger.debug(
                f"Connection added to room {tenant_aware_room_id} "
                f"(user_id={user_id}, tenant_id={tenant_id})"
            )

    async def disconnect(
        self,
        websocket: WebSocket,
        room_id: Hashable | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """
        Disconnect a WebSocket connection.

        If room_id and tenant_id are provided, disconnects from that specific room.
        If room_id is None, searches all rooms to find and remove the websocket.
        This is useful for unexpected disconnections where we don't know which room/tenant.
        """
        async with self._lock:
            if room_id is not None:
                # Direct disconnect from known room
                tenant_aware_room_id = self._get_tenant_aware_room_id(
                    room_id, tenant_id
                )
                conns = self._rooms.get(tenant_aware_room_id, [])
                self._rooms[tenant_aware_room_id] = [
                    c for c in conns if c.websocket is not websocket
                ]
                if not self._rooms[tenant_aware_room_id]:
                    del self._rooms[tenant_aware_room_id]
                    logger.debug(
                        f"Room {tenant_aware_room_id} removed (no connections)"
                    )
            else:
                # Search all rooms for this websocket (for unexpected disconnects)
                rooms_to_remove = []
                for room_id_key, conns in self._rooms.items():
                    filtered_conns = [c for c in conns if c.websocket is not websocket]
                    if len(filtered_conns) < len(conns):
                        # Found the connection in this room
                        found_conn = next(
                            (c for c in conns if c.websocket is websocket), None
                        )
                        if found_conn:
                            logger.debug(
                                f"Disconnecting websocket from room {room_id_key} "
                                f"(tenant_id={found_conn.tenant_id}, user_id={found_conn.user_id})"
                            )
                        if filtered_conns:
                            self._rooms[room_id_key] = filtered_conns
                        else:
                            rooms_to_remove.append(room_id_key)

                for room_id_key in rooms_to_remove:
                    del self._rooms[room_id_key]
                    logger.debug(f"Room {room_id_key} removed (no connections)")

    async def get_connection_stats(self) -> dict:
        """
        Get statistics about current connections, useful for debugging multi-tenant scenarios.

        Returns a dict with:
        - total_connections: total number of active connections
        - rooms_count: number of active rooms
        - connections_by_tenant: dict mapping tenant_id to connection count
        - connections_by_user: dict mapping user_id to connection count
        """
        async with self._lock:
            connections_by_tenant: Dict[str, int] = {}
            connections_by_user: Dict[UUID, int] = {}
            total = 0

            for room_id_key, conns in self._rooms.items():
                for conn in conns:
                    total += 1
                    tenant = conn.tenant_id or "none"
                    connections_by_tenant[tenant] = (
                        connections_by_tenant.get(tenant, 0) + 1
                    )
                    connections_by_user[conn.user_id] = (
                        connections_by_user.get(conn.user_id, 0) + 1
                    )

            return {
                "total_connections": total,
                "rooms_count": len(self._rooms),
                "connections_by_tenant": connections_by_tenant,
                "connections_by_user": {
                    str(k): v for k, v in connections_by_user.items()
                },
            }

    async def broadcast(
        self,
        room_id: Hashable,
        msg_type: str,
        current_user_id: UUID,
        payload: dict | None = None,
        required_topic: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        payload = payload or {}
        if msg_type == "takeover":
            payload["takeover_user_id"] = str(current_user_id)

        tenant_aware_room_id = self._get_tenant_aware_room_id(room_id, tenant_id)
        message = json.dumps({"type": msg_type, "payload": payload}, default=str)
        targets = list(self._rooms.get(tenant_aware_room_id, []))

        logger.debug(
            f"Broadcasting to room {tenant_aware_room_id} "
            f"(tenant_id={tenant_id}, targets={len(targets)})"
        )

        for conn in targets:
            if required_topic and required_topic not in conn.topics:
                continue
            try:
                await conn.websocket.send_text(message)
            except Exception as exc:
                logger.warning(
                    f"Failed to send message to websocket in room {tenant_aware_room_id}: {exc}"
                )
                # Disconnect from the specific room if we know it, otherwise search all rooms
                await self.disconnect(conn.websocket, room_id, conn.tenant_id)
