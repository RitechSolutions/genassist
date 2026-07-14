"""Tenant-scoped, opt-in Redis cache for web-scraper results.

The client is resolved lazily from the injector so there is no import cycle and no request scope is required.
Every path is wrapped so a cache miss, stale entry, or Redis outage silently degrades to a live fetch.
"""

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_KEY_PREFIX = "webscraper"
_MAX_AGE_CAP = 604800  # 7d ceiling on both TTL and read-side freshness


def _redis():
    # Avoids an injector import cycle at module load
    from app.dependencies.dependency_injection import RedisString
    from app.dependencies.injector import injector

    return injector.get(RedisString)


def build_cache_key(url: str, options: dict[str, Any]) -> str:
    """Tenant-scoped key: same url + options collapse to one entry per tenant.

    ``options`` carries request headers, so differing auth hashes to a distinct
    key and never shares across callers.
    """
    from app.core.tenant_scope import get_tenant_context

    raw = url + "|" + json.dumps(options, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"tenant:{get_tenant_context()}:{_KEY_PREFIX}:{digest}"


async def get_cached(url: str, options: dict[str, Any], max_age: int) -> dict[str, Any] | None:
    """Return a fresh cached result (with ``cacheState``/``cachedAt``) or ``None``."""
    max_age = min(max_age, _MAX_AGE_CAP)
    if max_age <= 0:
        return None
    try:
        raw = await _redis().get(build_cache_key(url, options))
        if not raw:
            return None
        payload = json.loads(raw)  # str: RedisString runs with decode_responses
        # honour a shorter read-side max_age even if the entry hasn't hit its TTL
        if time.time() - payload.get("_cachedAt", 0) > max_age:
            return None
        return {**payload["result"], "cacheState": "hit", "cachedAt": payload["_cachedAt"]}
    except Exception as exc:
        logger.warning("web scrape cache read failed for %s: %s", url, exc)
        return None


async def store(url: str, options: dict[str, Any], max_age: int, result: dict[str, Any]) -> None:
    """Cache a successful result under a self-expiring TTL; no-op otherwise."""
    max_age = min(max_age, _MAX_AGE_CAP)
    if max_age <= 0 or not result.get("success"):
        return
    try:
        payload = {"_cachedAt": time.time(), "result": result}
        await _redis().set(build_cache_key(url, options), json.dumps(payload, default=str), ex=max_age)
    except Exception as exc:
        logger.warning("web scrape cache write failed for %s: %s", url, exc)
