"""Unit tests for the tenant-scoped web-scrape result cache."""

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.utils import web_scrape_cache
from app.core.utils.web_scrape_cache import build_cache_key, get_cached, store

_URL = "https://example.com"
_OPTIONS = {"format": "markdown", "headers": {}}


def _fake_redis(get_return=None):
    return SimpleNamespace(get=AsyncMock(return_value=get_return), set=AsyncMock())


def _patch(redis, tenant="acme"):
    """Patch the module's redis + tenant lookups for a single call."""
    return (
        patch.object(web_scrape_cache, "_redis", return_value=redis),
        patch("app.core.tenant_scope.get_tenant_context", return_value=tenant),
    )


def test_build_cache_key_is_tenant_scoped_and_stable():
    with patch("app.core.tenant_scope.get_tenant_context", return_value="acme"):
        key = build_cache_key(_URL, _OPTIONS)
        again = build_cache_key(_URL, {"headers": {}, "format": "markdown"})  # order-insensitive
    assert key.startswith("tenant:acme:webscraper:")
    assert key == again  # sorted options ⇒ deterministic digest


def test_build_cache_key_differs_on_headers():
    with patch("app.core.tenant_scope.get_tenant_context", return_value="acme"):
        anon = build_cache_key(_URL, {"headers": {}})
        authed = build_cache_key(_URL, {"headers": {"authorization": "Bearer x"}})
    assert anon != authed  # differing auth never shares an entry


@pytest.mark.asyncio
async def test_max_age_zero_bypasses_redis():
    redis = _fake_redis()
    with patch.object(web_scrape_cache, "_redis", return_value=redis):
        assert await get_cached(_URL, _OPTIONS, 0) is None
    redis.get.assert_not_called()


@pytest.mark.asyncio
async def test_store_then_hit_round_trip():
    redis = _fake_redis()
    result = {"success": True, "content": "hi"}
    p_redis, p_tenant = _patch(redis)
    with p_redis, p_tenant:
        await store(_URL, _OPTIONS, 120, result)
        redis.get.return_value = redis.set.call_args.args[1]  # feed the stored payload back
        hit = await get_cached(_URL, _OPTIONS, 120)
    assert redis.set.call_args.kwargs["ex"] == 120
    assert hit["content"] == "hi"
    assert hit["cacheState"] == "hit"
    assert "cachedAt" in hit


@pytest.mark.asyncio
async def test_unsuccessful_result_is_not_stored():
    redis = _fake_redis()
    p_redis, p_tenant = _patch(redis)
    with p_redis, p_tenant:
        await store(_URL, _OPTIONS, 120, {"success": False})
    redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_stale_entry_is_a_miss():
    stale = json.dumps({"_cachedAt": time.time() - 500, "result": {"success": True}})
    redis = _fake_redis(get_return=stale)
    p_redis, p_tenant = _patch(redis)
    with p_redis, p_tenant:
        assert await get_cached(_URL, _OPTIONS, 120) is None  # 500s old > 120s max_age


@pytest.mark.asyncio
async def test_redis_error_falls_through_to_none():
    redis = SimpleNamespace(get=AsyncMock(side_effect=RuntimeError("down")), set=AsyncMock())
    p_redis, p_tenant = _patch(redis)
    with p_redis, p_tenant:
        assert await get_cached(_URL, _OPTIONS, 120) is None  # never raises
