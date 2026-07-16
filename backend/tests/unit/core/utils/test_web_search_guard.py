"""Unit tests for the web-search operational guards."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config.settings import settings
from app.core.utils import web_search_guard
from app.core.utils.web_search_guard import (
    build_request_fingerprint,
    check_enabled,
    check_tenant_rate,
    circuit_is_open,
    get_negative,
    mwmbl_circuit_is_open,
    record_block_event,
    record_mwmbl_failure,
    single_flight,
    store_negative,
)

_FP = "f" * 64
_ENVELOPE_KEYS = {"success", "query", "error", "count", "results", "text", "enrichedCount", "partial", "warnings"}


def _stateful_redis():
    store: dict[str, str] = {}
    ttls: dict[str, int] = {}

    async def _get(key):
        return store.get(key)

    async def _set(key, value, ex=None):
        store[key] = value
        if ex is not None:
            ttls[key] = ex

    async def _incr(key):
        store[key] = str(int(store.get(key, "0")) + 1)
        return int(store[key])

    async def _expire(key, ttl):
        ttls[key] = ttl
        return True

    return SimpleNamespace(
        get=AsyncMock(side_effect=_get),
        set=AsyncMock(side_effect=_set),
        incr=AsyncMock(side_effect=_incr),
        expire=AsyncMock(side_effect=_expire),
        store=store,
        ttls=ttls,
    )


def _patch(redis, tenant="acme"):
    return (
        patch.object(web_search_guard, "_redis", return_value=redis),
        patch("app.core.tenant_scope.get_tenant_context", return_value=tenant),
    )


def _freeze_time(at=1_000_000.0):
    return patch.object(web_search_guard, "time", SimpleNamespace(time=lambda: at))


def test_fingerprint_covers_every_result_affecting_option():
    base = {"maxResults": 5, "searchDepth": "basic", "region": "wt-wt", "excludeDomains": ["a.com"]}
    fingerprint = build_request_fingerprint("q", base)

    assert build_request_fingerprint("q", {**base, "region": "de-de"}) != fingerprint
    assert build_request_fingerprint("q", {**base, "searchDepth": "advanced"}) != fingerprint
    assert build_request_fingerprint("q", {**base, "excludeDomains": ["b.com"]}) != fingerprint
    assert build_request_fingerprint("other", base) != fingerprint


def test_fingerprint_ignores_option_order_list_order_and_max_age():
    a = build_request_fingerprint("q", {"maxResults": 5, "excludeDomains": ["b.com", "a.com"], "maxAge": 600})
    b = build_request_fingerprint("q", {"excludeDomains": ["a.com", "b.com"], "maxResults": 5, "maxAge": 0})
    c = build_request_fingerprint("q", {"excludeDomains": ["a.com", "b.com"], "maxResults": 5})

    assert a == b == c


def test_check_enabled_reads_the_kill_switch(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", False)
    assert check_enabled() is False
    monkeypatch.setattr(settings, "WEB_SEARCH_ENABLED", True)
    assert check_enabled() is True


@pytest.mark.asyncio
async def test_acquire_global_slot_bounds_concurrency():
    free = web_search_guard._global_semaphore._value
    async with web_search_guard.acquire_global_slot():
        assert web_search_guard._global_semaphore._value == free - 1
    assert web_search_guard._global_semaphore._value == free


@pytest.mark.asyncio
async def test_tenant_rate_increments_and_trips_at_the_limit(monkeypatch):
    monkeypatch.setattr(settings, "WEB_SEARCH_TENANT_PER_MINUTE", 3)
    redis = _stateful_redis()
    with patch.object(web_search_guard, "_redis", return_value=redis), _freeze_time():
        allowed = [await check_tenant_rate("acme") for _ in range(4)]

    assert allowed == [True, True, True, False]
    key = redis.incr.call_args.args[0]
    assert key.startswith("websearch:rl:acme:")
    redis.expire.assert_awaited_once()  # TTL set only when the window key is created


@pytest.mark.asyncio
async def test_tenant_rate_degrades_open_on_redis_error():
    redis = SimpleNamespace(incr=AsyncMock(side_effect=RuntimeError("down")))
    with patch.object(web_search_guard, "_redis", return_value=redis):
        assert await check_tenant_rate("acme") is True


@pytest.mark.asyncio
async def test_single_flight_coalesces_and_charges_the_leader_once():
    release = asyncio.Event()
    rate_charges = AsyncMock()
    producer_calls: list[int] = []

    async def producer():
        producer_calls.append(1)
        await rate_charges("acme")
        await release.wait()
        return {"success": True, "results": [{"title": "x"}]}

    tasks = [asyncio.create_task(single_flight("acme", _FP, producer)) for _ in range(5)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(*tasks)

    assert len(producer_calls) == 1
    rate_charges.assert_awaited_once()
    assert all(result == results[0] for result in results)


@pytest.mark.asyncio
async def test_single_flight_followers_get_deep_copies():
    release = asyncio.Event()

    async def producer():
        await release.wait()
        return {"success": True, "results": [{"title": "x"}]}

    tasks = [asyncio.create_task(single_flight("acme", _FP, producer)) for _ in range(3)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    release.set()
    leader, follower_a, follower_b = await asyncio.gather(*tasks)

    assert leader == follower_a == follower_b
    assert follower_a is not follower_b
    assert follower_a["results"] is not follower_b["results"]
    follower_a["results"].append({"title": "mutation"})
    assert len(follower_b["results"]) == 1
    assert len(leader["results"]) == 1


@pytest.mark.asyncio
async def test_single_flight_distinct_fingerprints_do_not_coalesce():
    release = asyncio.Event()
    producer_calls: list[str] = []

    def make_producer(name):
        async def producer():
            producer_calls.append(name)
            await release.wait()
            return {"success": True}

        return producer

    tasks = [
        asyncio.create_task(single_flight("acme", "a" * 64, make_producer("a"))),
        asyncio.create_task(single_flight("acme", "b" * 64, make_producer("b"))),
    ]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(*tasks)

    assert sorted(producer_calls) == ["a", "b"]


@pytest.mark.asyncio
async def test_single_flight_leader_failure_resolves_followers_without_raising():
    release = asyncio.Event()

    async def producer():
        await release.wait()
        raise RuntimeError("boom at https://duckduckgo.com/html/?q=XYZZY-CANARY-QUERY")

    tasks = [asyncio.create_task(single_flight("acme", _FP, producer)) for _ in range(3)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.gather(*tasks)

    assert all(result["success"] is False for result in results)
    assert all(set(result) == _ENVELOPE_KEYS for result in results)
    assert all("XYZZY-CANARY-QUERY" not in result["error"] for result in results)


@pytest.mark.asyncio
async def test_single_flight_cleans_the_inflight_map():
    async def producer():
        return {"success": True}

    async def failing_producer():
        raise RuntimeError("boom")

    await single_flight("acme", _FP, producer)
    assert web_search_guard._inflight == {}
    await single_flight("acme", _FP, failing_producer)
    assert web_search_guard._inflight == {}


@pytest.mark.asyncio
async def test_negative_cache_roundtrip_ttls_and_expiry():
    redis = _stateful_redis()
    p_redis, p_tenant = _patch(redis)
    with p_redis, p_tenant, _freeze_time():
        await store_negative(_FP, "blocked")
        assert await get_negative(_FP) == "blocked"
        key = redis.set.call_args.args[0]
        assert key.startswith("tenant:acme:websearch-neg:")
        assert redis.ttls[key] == 120
        await store_negative(_FP, "timeout")
        assert redis.ttls[key] == 60
        redis.store.pop(key)
        assert await get_negative(_FP) is None


@pytest.mark.asyncio
async def test_negative_cache_degrades_open_on_redis_error():
    redis = SimpleNamespace(
        get=AsyncMock(side_effect=RuntimeError("down")), set=AsyncMock(side_effect=RuntimeError("down"))
    )
    p_redis, p_tenant = _patch(redis)
    with p_redis, p_tenant:
        await store_negative(_FP, "blocked")
        assert await get_negative(_FP) is None


@pytest.mark.asyncio
async def test_circuit_opens_on_first_block_and_closes_on_expiry():
    redis = _stateful_redis()
    with patch.object(web_search_guard, "_redis", return_value=redis), _freeze_time():
        assert await circuit_is_open() is False
        await record_block_event()
        assert await circuit_is_open() is True
        assert redis.ttls["websearch:cb:open"] == 900
        redis.store.pop("websearch:cb:open")
        assert await circuit_is_open() is False


@pytest.mark.asyncio
async def test_circuit_degrades_open_on_redis_error():
    redis = SimpleNamespace(
        get=AsyncMock(side_effect=RuntimeError("down")), set=AsyncMock(side_effect=RuntimeError("down"))
    )
    with patch.object(web_search_guard, "_redis", return_value=redis):
        await record_block_event()  # must not raise
        assert await circuit_is_open() is False


@pytest.mark.asyncio
async def test_mwmbl_cooldown_opens_on_failure_and_closes_on_expiry():
    redis = _stateful_redis()
    with patch.object(web_search_guard, "_redis", return_value=redis), _freeze_time():
        assert await mwmbl_circuit_is_open() is False
        await record_mwmbl_failure()
        assert await mwmbl_circuit_is_open() is True
        assert redis.ttls["websearch:mwmbl:cooldown"] == 300
        redis.store.pop("websearch:mwmbl:cooldown")
        assert await mwmbl_circuit_is_open() is False


@pytest.mark.asyncio
async def test_mwmbl_cooldown_degrades_open_on_redis_error():
    redis = SimpleNamespace(
        get=AsyncMock(side_effect=RuntimeError("down")), set=AsyncMock(side_effect=RuntimeError("down"))
    )
    with patch.object(web_search_guard, "_redis", return_value=redis):
        await record_mwmbl_failure()  # must not raise
        assert await mwmbl_circuit_is_open() is False
