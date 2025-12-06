from fastapi_injector import Injected
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from redis import Redis
import os
from typing import Optional

from app.schemas.api_key import ApiKeyRead

logger = logging.getLogger(__name__)


@Injected
class QuotaService:
    def __init__(
        self,
        db: AsyncSession = Injected(AsyncSession),
        redis_client: Optional[Redis] = None,
    ):
        self.db = db
        self.redis_client = redis_client or Redis(
            host=os.environ.get("REDIS_HOST", "redis"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            db=0,
            decode_responses=True,
        )

    async def enforce_quota(self, api_key: ApiKeyRead):
        """
        Enforce usage quota for a given API key using a sliding window algorithm with Redis.
        """
        # TODO enforce quota, adding db_field
        # now = int(time.time())
        # window_start = now - project_params.DEFAULT_WINDOW_SECONDS
        # redis_key = f"quota:{api_key.id}"
        #
        # # Remove old timestamps
        # self.redis_client.zremrangebyscore(redis_key, 0, window_start)
        #
        # # Count how many requests are in the window
        # request_count = self.redis_client.zcard(redis_key)
        #
        # # Check quota
        # if request_count >= api_key.usage_quota:
        #     logger.warning(f"Quota exceeded for API key {api_key.id}")
        #     raise AppException(status_code=429, error_key=ErrorKey.QUOTA_EXCEEDED)
        #
        # # Add the current timestamp
        # self.redis_client.zadd(redis_key, {now: now})
        # self.redis_client.expire(redis_key, project_params.DEFAULT_WINDOW_SECONDS)
        pass
