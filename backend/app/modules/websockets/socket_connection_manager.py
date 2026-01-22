from __future__ import annotations
import asyncio
import json
import logging
from contextvars import copy_context, Context
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
    # Captured context from connection time (includes starlette_context, tenant context, etc.)
    context: Context | None = field(default=None, repr=False)

class SocketConnectionManager:
    """
    Global singleton for managing WebSocket rooms with optional Redis Pub/Sub support
    for horizontal scaling across multiple server instances.

    When Redis is available:
    - Messages are published to Redis Pub/Sub channels
    - Each server subscribes to Redis and delivers messages to its local WebSocket connections
    - Supports multiple server instances (horizontal scaling)

    When Redis is not available:
    - Falls back to local-only broadcasting (single server mode)
    - Maintains backward compatibility with existing deployments
    """

    def __init__(self, redis_manager=None) -> None:
        self._rooms: Dict[Hashable, List[Connection]] = {}
        self._lock = asyncio.Lock()
        self._redis_manager = redis_manager
        self._redis_subscriber_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

    def _get_tenant_aware_room_id(self, room_id: Hashable, tenant_id: str | None) -> Hashable:
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

        # CRITICAL FIX: Extract the raw Starlette WebSocket from FastAPI's wrapper
        # FastAPI/InjectorMiddleware wraps WebSocket with context-checking proxies
        # We need the raw WebSocket for background task sends (outside request context)
        raw_websocket = websocket
        if hasattr(websocket, '_websocket'):
            # FastAPI wraps Starlette's WebSocket, get the underlying one
            raw_websocket = websocket._websocket
            logger.debug(f"[CONNECT] Extracted raw Starlette WebSocket")
        elif hasattr(websocket, '__wrapped__'):
            # Check for other wrapper patterns
            raw_websocket = websocket.__wrapped__
            logger.debug(f"[CONNECT] Extracted unwrapped WebSocket")

        logger.info(f"[CONNECT] WebSocket type: {type(websocket)}, Raw type: {type(raw_websocket)}")

        # Capture the current context (includes starlette_context, tenant context, etc.)
        # This allows sends from background tasks to run within the original request context
        captured_context = copy_context()
        logger.debug(f"[CONNECT] Captured context for user {user_id}")

        async with self._lock:
            self._rooms.setdefault(tenant_aware_room_id, []).append(
                Connection(raw_websocket, user_id, permissions, tenant_id, set(topics), captured_context)
            )
            logger.info(
                f"[CONNECT] Added to room {tenant_aware_room_id} "
                f"(raw_room_id={room_id}, user_id={user_id}, tenant_id={tenant_id}, topics={topics})"
            )
            logger.info(f"[CONNECT] Total rooms: {len(self._rooms)}, Connections in this room: {len(self._rooms[tenant_aware_room_id])}")

    async def disconnect(
        self,
        websocket: WebSocket,
        room_id: Hashable | None = None,
        tenant_id: str | None = None
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
                tenant_aware_room_id = self._get_tenant_aware_room_id(room_id, tenant_id)
                conns = self._rooms.get(tenant_aware_room_id, [])
                self._rooms[tenant_aware_room_id] = [c for c in conns if c.websocket is not websocket]
                if not self._rooms[tenant_aware_room_id]:
                    del self._rooms[tenant_aware_room_id]
                    logger.debug(f"Room {tenant_aware_room_id} removed (no connections)")
            else:
                # Search all rooms for this websocket (for unexpected disconnects)
                rooms_to_remove = []
                for room_id_key, conns in self._rooms.items():
                    filtered_conns = [c for c in conns if c.websocket is not websocket]
                    if len(filtered_conns) < len(conns):
                        # Found the connection in this room
                        found_conn = next((c for c in conns if c.websocket is websocket), None)
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
                    connections_by_tenant[tenant] = connections_by_tenant.get(tenant, 0) + 1
                    connections_by_user[conn.user_id] = connections_by_user.get(conn.user_id, 0) + 1

            return {
                "total_connections": total,
                "rooms_count": len(self._rooms),
                "connections_by_tenant": connections_by_tenant,
                "connections_by_user": {str(k): v for k, v in connections_by_user.items()},
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
        """
        Broadcast a message to all connections in a room.

        If Redis is available, publishes the message to Redis Pub/Sub for delivery
        across all server instances. Otherwise, delivers only to local connections.
        """
        payload = payload or {}
        if msg_type == "takeover":
            payload["takeover_user_id"] = str(current_user_id)

        tenant_aware_room_id = self._get_tenant_aware_room_id(room_id, tenant_id)

        # Publish to Redis for multi-server broadcasting (if available)
        if self._redis_manager:
            try:
                redis_channel = self._get_redis_channel(tenant_aware_room_id)
                message_data = {
                    "type": msg_type,
                    "payload": payload,
                    "required_topic": required_topic,
                    "room_id": str(room_id),
                    "tenant_id": tenant_id,
                }
                redis_client = await self._redis_manager.get_redis()
                await redis_client.publish(
                    redis_channel,
                    json.dumps(message_data, default=str)
                )
                logger.info(
                    f"[BROADCAST] Published to Redis channel: {redis_channel} | "
                    f"Room: {tenant_aware_room_id} | Type: {msg_type} | Topic: {required_topic}"
                )
                # Message will be delivered via Redis subscriber
                return
            except Exception as exc:
                logger.warning(
                    f"Failed to publish to Redis, falling back to local broadcast: {exc}"
                )

        # Fallback to local-only broadcasting (single server mode or Redis failure)
        await self._broadcast_local(
            tenant_aware_room_id=tenant_aware_room_id,
            msg_type=msg_type,
            payload=payload,
            required_topic=required_topic,
            room_id=room_id,
            tenant_id=tenant_id,
        )

    async def _broadcast_local(
        self,
        tenant_aware_room_id: Hashable,
        msg_type: str,
        payload: dict,
        required_topic: str | None = None,
        room_id: Hashable | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """
        Broadcast a message to local WebSocket connections only.
        Used for single-server mode or as fallback when Redis is unavailable.
        """
        message = json.dumps({"type": msg_type, "payload": payload}, default=str)
        targets = list(self._rooms.get(tenant_aware_room_id, []))

        logger.info(
            f"[BROADCAST_LOCAL] Room: {tenant_aware_room_id} | "
            f"Targets: {len(targets)} | Type: {msg_type} | Topic: {required_topic}"
        )
        logger.info(f"[BROADCAST_LOCAL] Current _rooms keys: {list(self._rooms.keys())}")
        logger.info(f"[BROADCAST_LOCAL] Total rooms: {len(self._rooms)}")

        for conn in targets:
            if required_topic and required_topic not in conn.topics:
                continue
            try:
                # Run the send within the captured context from connection time
                # This makes starlette_context and tenant context available to the WebSocket
                if conn.context:
                    def _send_sync():
                        """Sync wrapper to run async send in context"""
                        return asyncio.create_task(conn.websocket.send_text(message))

                    # Run in the captured context
                    task = conn.context.run(_send_sync)
                    await task
                    logger.debug(f"[BROADCAST_LOCAL] ✅ Sent within captured context to user {conn.user_id}")
                else:
                    # Fallback: send without context (might fail)
                    await conn.websocket.send_text(message)
                    logger.debug(f"[BROADCAST_LOCAL] ✅ Sent without context to user {conn.user_id}")

            except Exception as exc:
                logger.warning(
                    f"[BROADCAST_LOCAL] ❌ Failed to send to user {conn.user_id}: {exc}"
                )
                # Disconnect from the specific room if we know it, otherwise search all rooms
                if "context" not in str(exc).lower():
                    await self.disconnect(conn.websocket, room_id, conn.tenant_id)

    # ------------ Redis Pub/Sub methods -------------------------------------------------

    def _get_redis_channel(self, tenant_aware_room_id: Hashable) -> str:
        """Get Redis Pub/Sub channel name for a room."""
        return f"websocket:{tenant_aware_room_id}"

    async def initialize_redis_subscriber(self) -> None:
        """
        Initialize Redis Pub/Sub subscriber for receiving messages from other server instances.
        This should be called during application startup if Redis is available.
        """
        if not self._redis_manager:
            logger.info("Redis not configured, running in single-server mode")
            return

        # Clean up any existing subscriber task before creating a new one
        if self._redis_subscriber_task and not self._redis_subscriber_task.done():
            logger.warning("Redis subscriber already running, skipping initialization")
            return
        elif self._redis_subscriber_task and self._redis_subscriber_task.done():
            # Previous task completed/crashed, check for exceptions
            try:
                exc = self._redis_subscriber_task.exception()
                if exc:
                    logger.error(f"Previous Redis subscriber task failed with: {exc}")
            except (asyncio.CancelledError, asyncio.InvalidStateError):
                pass
            logger.info("Reinitializing Redis subscriber after previous task completed")

        # Reset shutdown event for new subscriber
        self._shutdown_event.clear()
        self._redis_subscriber_task = asyncio.create_task(self._redis_subscriber_loop())
        logger.info("Redis subscriber initialized for WebSocket message distribution")

    async def _redis_subscriber_loop(self) -> None:
        """
        Background task that subscribes to Redis Pub/Sub channels and delivers messages
        to local WebSocket connections.
        """
        pubsub = None
        try:
            redis_client = await self._redis_manager.get_redis()
            pubsub = redis_client.pubsub()

            # Subscribe to pattern that matches all websocket channels
            await pubsub.psubscribe("websocket:*")
            logger.info("Subscribed to Redis pattern: websocket:*")

            while not self._shutdown_event.is_set():
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0
                    )

                    if message and message["type"] == "pmessage":
                        await self._handle_redis_message(message)

                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    logger.info("Redis subscriber loop cancelled")
                    break
                except Exception as exc:
                    logger.error(f"Error processing Redis message: {exc}")
                    await asyncio.sleep(1)

        except Exception as exc:
            logger.error(f"Redis subscriber loop error: {exc}")
        finally:
            # Ensure pubsub connection is always closed to prevent leaks
            if pubsub is not None:
                try:
                    await pubsub.punsubscribe("websocket:*")
                    await pubsub.close()
                    logger.info("Redis pubsub connection closed successfully")
                except Exception as exc:
                    logger.error(f"Error closing Redis pubsub: {exc}")
            logger.info("Redis subscriber loop stopped")

    async def _handle_redis_message(self, message: dict) -> None:
        """
        Handle incoming Redis Pub/Sub message and deliver to local WebSocket connections.
        """
        try:
            channel = message["channel"]
            data = json.loads(message["data"])

            msg_type = data.get("type")
            payload = data.get("payload", {})
            required_topic = data.get("required_topic")
            room_id = data.get("room_id")
            tenant_id = data.get("tenant_id")

            tenant_aware_room_id = self._get_tenant_aware_room_id(room_id, tenant_id)

            logger.debug(
                f"[REDIS_RECEIVED] Channel: {channel} | "
                f"Room ID from data: {room_id} | Tenant ID: {tenant_id} | "
                f"Reconstructed room: {tenant_aware_room_id} | Type: {msg_type} | Topic: {required_topic}"
            )

            # Deliver to local connections
            await self._broadcast_local(
                tenant_aware_room_id=tenant_aware_room_id,
                msg_type=msg_type,
                payload=payload,
                required_topic=required_topic,
                room_id=room_id,
                tenant_id=tenant_id,
            )

        except Exception as exc:
            logger.error(f"Error handling Redis message: {exc}")

    async def cleanup(self) -> None:
        """
        Cleanup Redis subscriber and close all connections.
        This should be called during application shutdown.
        """
        logger.info("Cleaning up SocketConnectionManager...")

        # Signal shutdown to subscriber loop
        self._shutdown_event.set()

        # Wait for subscriber task to finish
        if self._redis_subscriber_task and not self._redis_subscriber_task.done():
            try:
                await asyncio.wait_for(self._redis_subscriber_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Redis subscriber task did not finish in time")
                self._redis_subscriber_task.cancel()
            except Exception as exc:
                logger.error(f"Error waiting for subscriber task: {exc}")

        logger.info("SocketConnectionManager cleanup complete")
