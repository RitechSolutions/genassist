import asyncio
import hashlib
import logging
import time
from collections import OrderedDict

import httpx

from config import settings
# Shared schemas
from backend_shared.schemas.auth import VerifyTokenRequest, AuthenticatedUser

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class TokenVerifier:
    """
    Verifies tokens by calling the backend's internal endpoint once,
    then caches the result in-memory keyed by token hash until expiry.
    """

    def __init__(self):
        self._cache: OrderedDict[str, AuthenticatedUser] = OrderedDict()
        self._client = httpx.AsyncClient(timeout=5.0)
        self._sweep_task: asyncio.Task | None = None

    async def start(self):
        self._sweep_task = asyncio.create_task(self._sweep_loop())

    async def stop(self):
        if self._sweep_task and not self._sweep_task.done():
            self._sweep_task.cancel()
            try:
                await self._sweep_task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()

    async def verify(
        self,
        access_token: str | None,
        api_key: str | None,
        required_permissions: list[str],
        tenant_id: str,
    ) -> AuthenticatedUser:
        cache_key = self._cache_key(access_token, api_key)

        # Check cache
        cached = self._cache.get(cache_key)
        if cached and (cached.token_exp is None or cached.token_exp > time.time() + 30):
            self._cache.move_to_end(cache_key)
            return cached

        # Call backend
        try:
            payload = VerifyTokenRequest(
                access_token=access_token,
                api_key=api_key,
                required_permissions=required_permissions,
                tenant_id=tenant_id,
            )

            resp = await self._client.post(
                f"{settings.BACKEND_URL}/api/internal/ws/verify-token",
                json=payload.model_dump(mode="json"),
                headers={"x-internal-secret": settings.WS_INTERNAL_SECRET},
            )
        except httpx.RequestError as exc:
            logger.error(f"Backend unreachable for token verification: {exc}")
            raise AuthenticationError(503, "Backend unavailable")

        if resp.status_code != 200:
            detail = resp.json().get("detail", "Authentication failed")
            raise AuthenticationError(resp.status_code, detail)

        data = resp.json()
        user = AuthenticatedUser(
            user_id=data["user_id"],
            permissions=data["permissions"],
            tenant_id=data["tenant_id"],
            token_exp=data.get("token_exp"),
        )

        # Store in cache with LRU eviction
        self._cache[cache_key] = user
        self._cache.move_to_end(cache_key)
        if len(self._cache) > settings.AUTH_CACHE_MAX_SIZE:
            self._cache.popitem(last=False)

        return user

    def _cache_key(self, access_token: str | None, api_key: str | None) -> str:
        raw = access_token or api_key or ""
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _sweep_loop(self):
        """Remove expired cache entries every 60 seconds."""
        while True:
            try:
                await asyncio.sleep(60)
                now = time.time()
                expired = [
                    k for k, v in self._cache.items()
                    if v.token_exp is not None and v.token_exp <= now
                ]
                for k in expired:
                    del self._cache[k]
                if expired:
                    logger.debug(f"Swept {len(expired)} expired auth cache entries")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Auth cache sweep error: {exc}")
