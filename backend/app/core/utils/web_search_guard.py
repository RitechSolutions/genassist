"""Operational guards for the web-search engine.

Kill switch, per-tenant rate limit, per-process single-flight coalescing and global
concurrency, tenant-scoped negative caching, a deployment-global DuckDuckGo circuit
breaker, and a short deployment-global Mwmbl fallback cooldown.

Every Redis-backed guard degrades open — an unreachable Redis never blocks a search.
No key or log line carries a raw query, URL, or snippet: callers pass an opaque request fingerprint built over
every result-affecting option.
"""

import asyncio
import copy
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.utils.web_search_utils import WebSearchEnvelope, _sanitize_error

logger = logging.getLogger(__name__)

_GLOBAL_CONCURRENCY = 4
_RATE_WINDOW_SECONDS = 60
_NEGATIVE_TTL_SECONDS = 60
_NEGATIVE_BLOCKED_TTL_SECONDS = 120
_CIRCUIT_OPEN_TTL_SECONDS = 900  # fixed 15-minute cooldown
_MWMBL_COOLDOWN_TTL_SECONDS = 300  # short pause after a Mwmbl failure, deployment-wide

_global_semaphore = asyncio.Semaphore(_GLOBAL_CONCURRENCY)
_inflight: dict[str, asyncio.Future] = {}


def _redis():
    # Avoids an injector import cycle at module load
    from app.dependencies.dependency_injection import RedisString
    from app.dependencies.injector import injector

    return injector.get(RedisString)


def build_request_fingerprint(query: str, options: dict[str, Any]) -> str:
    """Hash of the query and every option that can change the results.

    ``maxAge`` is left out because it only affects cache freshness, not the
    answer itself. Lists are sorted so the same options in a different order
    still match. Cache hits and in-flight deduping both use this key, so two
    searches share a result only when they would return the same thing.
    """
    canonical = {
        key: sorted(value) if isinstance(value, (list, tuple)) else value
        for key, value in options.items()
        if key != "maxAge"
    }
    raw = json.dumps({"query": query, "options": canonical}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def check_enabled() -> bool:
    """Kill switch; False means fail fast with no upstream traffic."""
    from app.core.config.settings import settings

    return bool(settings.WEB_SEARCH_ENABLED)


def acquire_global_slot() -> asyncio.Semaphore:
    """Per-process concurrency bound around SERP fetches."""
    return _global_semaphore


async def check_tenant_rate(tenant: str) -> bool:
    """Per-tenant rate limit over a one-minute window. Returns True if the search may run.

    Only the request that actually performs the search spends a slot; duplicates
    waiting on the same in-flight search are not counted. The Redis key stores
    only the tenant id and a counter — never the query.
    """
    from app.core.config.settings import settings

    key = f"websearch:rl:{tenant}:{int(time.time() // _RATE_WINDOW_SECONDS)}"
    try:
        redis = _redis()
        count = await redis.incr(key)
        if count == 1:
            # outlive the window; the epoch-minute key never rolls into the next one
            await redis.expire(key, _RATE_WINDOW_SECONDS * 2)
        return count <= settings.WEB_SEARCH_TENANT_PER_MINUTE
    except Exception as exc:
        logger.warning("web search rate-limit check degraded open: %s", exc)
        return True


def _producer_failure_envelope(exc: Exception) -> WebSearchEnvelope:
    """Standard failure response when the search run crashes."""
    message = _sanitize_error(exc)
    return {
        "success": False,
        "query": "",
        "error": message,
        "count": 0,
        "results": [],
        "text": f"Web search failed: {message}",
        "enrichedCount": 0,
        "partial": False,
        "warnings": [],
    }


async def single_flight(
    tenant: str, fingerprint: str, producer: Callable[[], Awaitable[WebSearchEnvelope]]
) -> WebSearchEnvelope:
    """If several identical searches start at once, run ``producer()`` only once.

    The first caller does the real work (search, enrich, cache). The others wait
    for that same result and each get their own deep copy, so they don't share
    one mutable response object. If the producer fails, everyone gets a standard
    failure response — followers never see a raised exception.
    """
    key = f"{tenant}:{fingerprint}"
    existing = _inflight.get(key)
    if existing is not None:
        return copy.deepcopy(await asyncio.shield(existing))

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _inflight[key] = future
    try:
        try:
            result = await producer()
        except Exception as exc:
            logger.warning("web search single-flight producer failed: %s", _sanitize_error(exc))
            result = _producer_failure_envelope(exc)
        if not future.done():
            future.set_result(result)
        return result
    finally:
        _inflight.pop(key, None)
        if not future.done():
            future.cancel()


def _negative_key(fingerprint: str) -> str:
    from app.core.tenant_scope import get_tenant_context

    return f"tenant:{get_tenant_context()}:websearch-neg:{fingerprint}"


async def get_negative(fingerprint: str) -> str | None:
    """Return the recently-failed category for this fingerprint, or ``None``."""
    try:
        raw = await _redis().get(_negative_key(fingerprint))
        if not raw:
            return None
        return json.loads(raw).get("category") or None
    except Exception as exc:
        logger.warning("web search negative-cache read degraded open: %s", exc)
        return None


async def store_negative(fingerprint: str, category: str) -> None:
    """Cache a provider failure briefly so the same search isn't retried immediately."""
    ttl = _NEGATIVE_BLOCKED_TTL_SECONDS if category == "blocked" else _NEGATIVE_TTL_SECONDS
    try:
        payload = json.dumps({"category": category, "at": time.time()})
        await _redis().set(_negative_key(fingerprint), payload, ex=ttl)
    except Exception as exc:
        logger.warning("web search negative-cache write degraded open: %s", exc)


async def circuit_is_open() -> bool:
    try:
        return bool(await _redis().get("websearch:cb:open"))
    except Exception as exc:
        logger.warning("web search circuit check degraded open: %s", exc)
        return False


async def record_block_event() -> None:
    """Trip the shared DuckDuckGo circuit breaker on the first block."""
    try:
        await _redis().set("websearch:cb:open", "1", ex=_CIRCUIT_OPEN_TTL_SECONDS)
    except Exception as exc:
        logger.warning("web search circuit record degraded open: %s", exc)


async def mwmbl_circuit_is_open() -> bool:
    try:
        return bool(await _redis().get("websearch:mwmbl:cooldown"))
    except Exception as exc:
        logger.warning("web search mwmbl cooldown check degraded open: %s", exc)
        return False


async def record_mwmbl_failure() -> None:
    """Pause Mwmbl fallback for a short cooldown after it fails."""
    try:
        await _redis().set("websearch:mwmbl:cooldown", "1", ex=_MWMBL_COOLDOWN_TTL_SECONDS)
    except Exception as exc:
        logger.warning("web search mwmbl cooldown record degraded open: %s", exc)
