import asyncio
import logging
import time

from connections.manager import ConnectionManager
from config import settings

logger = logging.getLogger(__name__)


async def heartbeat_loop(manager: ConnectionManager):
    """
    Periodically sends WebSocket ping frames to all connections
    and removes those that haven't responded within the timeout.
    """
    interval = settings.HEARTBEAT_INTERVAL
    timeout = settings.HEARTBEAT_TIMEOUT

    while True:
        try:
            await asyncio.sleep(interval)
            now = time.time()

            for room_id, connections in list(manager.rooms.items()):
                for conn in list(connections):
                    # Check if connection missed the last pong
                    if now - conn.last_pong > interval + timeout:
                        logger.info(
                            f"[HEARTBEAT] Dead connection detected: user={conn.user_id} "
                            f"room={room_id} last_pong={now - conn.last_pong:.0f}s ago"
                        )
                        try:
                            await conn.websocket.close(code=1001, reason="Pong timeout")
                        except Exception:
                            pass
                        await manager.disconnect(conn.websocket)
                        continue

                    # Send ping
                    try:
                        await conn.websocket.send_json({"type": "ping"})
                        # Note: browser WebSocket protocol-level ping/pong is handled
                        # automatically by uvicorn. This is an application-level ping
                        # for connection liveness detection. The client should respond
                        # with {"type": "pong"} or the protocol-level pong suffices
                        # to keep last_pong updated.
                    except Exception:
                        logger.debug(f"[HEARTBEAT] Ping failed for user={conn.user_id}")
                        await manager.disconnect(conn.websocket)

        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")
            break
        except Exception as exc:
            logger.error(f"Heartbeat loop error: {exc}")
            await asyncio.sleep(5)
