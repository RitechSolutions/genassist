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
            decode_responses=True
        )

    async def enforce_quota(self, api_key: ApiKeyRead):
        """
        Enforce usage quota for a given API key using a sliding window algorithm with Redis.
        """
        # TODO: enforce the quota (needs a usage-quota field on the API key).
        pass

