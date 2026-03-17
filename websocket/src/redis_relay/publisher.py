import json
import logging

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisPublisher:
    """
    Publishes client-sent WebSocket messages upstream to the backend via Redis.
    Channel pattern: ws_upstream:{tenant_id}:{room_id}
    """

    def __init__(self, redis_client: aioredis.Redis):
        self._redis = redis_client

    async def publish_upstream(
        self,
        tenant_id: str,
        room_id: str,
        user_id: str,
        data: str,
    ):
        channel = f"ws_upstream:{tenant_id}:{room_id}"
        message = json.dumps({
            "user_id": user_id,
            "tenant_id": tenant_id,
            "room_id": room_id,
            "data": data,
        })
        try:
            await self._redis.publish(channel, message)
        except Exception as exc:
            logger.warning(f"Failed to publish upstream message: {exc}")
