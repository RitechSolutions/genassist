import asyncio
import json
import logging

import redis.asyncio as aioredis

from connections.manager import ConnectionManager

logger = logging.getLogger(__name__)


class RedisSubscriber:
    """
    Subscribes to Redis websocket:* channels and delivers messages
    to local WebSocket connections via ConnectionManager.
    """

    def __init__(self, redis_client: aioredis.Redis, manager: ConnectionManager):
        self._redis = redis_client
        self._manager = manager
        self._task: asyncio.Task | None = None
        self._shutdown = asyncio.Event()

    async def start(self):
        self._shutdown.clear()
        self._task = asyncio.create_task(self._subscribe_loop())
        logger.info("Redis subscriber started")

    async def stop(self):
        self._shutdown.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            except Exception:
                pass
        logger.info("Redis subscriber stopped")

    async def _subscribe_loop(self):
        backoff = 1
        while not self._shutdown.is_set():
            pubsub = None
            try:
                pubsub = self._redis.pubsub()
                await pubsub.psubscribe("websocket:*")
                logger.info("Subscribed to Redis pattern: websocket:*")
                backoff = 1  # Reset on successful subscribe

                while not self._shutdown.is_set():
                    try:
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=1.0,
                        )
                        if message and message["type"] == "pmessage":
                            await self._handle_message(message)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        return
                    except Exception as exc:
                        logger.error(f"Error processing Redis message: {exc}")
                        await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.error(f"Redis subscriber connection error: {exc}")
                await asyncio.sleep(min(backoff, 30))
                backoff = min(backoff * 2, 30)
            finally:
                if pubsub:
                    try:
                        await pubsub.punsubscribe("websocket:*")
                        await pubsub.close()
                    except Exception:
                        pass

    async def _handle_message(self, message: dict):
        try:
            data = json.loads(message["data"])
            msg_type = data.get("type")
            payload = data.get("payload", {})
            required_topic = data.get("required_topic")
            room_id = data.get("room_id")
            tenant_id = data.get("tenant_id")

            tenant_aware_room_id = (
                f"{tenant_id}:{room_id}" if tenant_id else str(room_id)
            )

            await self._manager.broadcast_to_room(
                tenant_aware_room_id=tenant_aware_room_id,
                msg_type=msg_type,
                payload=payload,
                required_topic=required_topic,
            )
        except Exception as exc:
            logger.error(f"Error handling Redis message: {exc}")
