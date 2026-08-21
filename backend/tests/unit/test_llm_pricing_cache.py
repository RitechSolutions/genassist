"""Unit tests for the per-tenant rate cache: TTL refresh, invalidation, single-flight and DB-failure behaviour"""

import threading

import pytest

import app.services.llm_pricing_cache as pricing_cache
from app.services.llm_pricing_cache import (
    get_db_pricing_nested,
    invalidate_llm_cost_rates_cache,
)

TENANT = "acme"
RATES = {"openai": {"gpt-4o": {"input_per_1k": 0.005, "output_per_1k": 0.02}}}
NEWER = {"openai": {"gpt-4o": {"input_per_1k": 0.009, "output_per_1k": 0.03}}}


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def advance(self, seconds):
        self.now += seconds

    def __call__(self):
        return self.now


class Loader:

    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    def __call__(self, tenant):
        self.calls += 1
        return self.results[min(self.calls - 1, len(self.results) - 1)]


class BlockingLoader(Loader):

    def __init__(self, *results, block_on=1):
        super().__init__(*results)
        self.block_on = block_on
        self.entered = threading.Event()
        self.released = threading.Event()

    def __call__(self, tenant):
        result = super().__call__(tenant)
        if self.calls == self.block_on:
            self.entered.set()
            assert self.released.wait(5), "the parked load was never released"
        return result


def _reset():
    invalidate_llm_cost_rates_cache()
    pricing_cache._refreshing.clear()


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(pricing_cache.time, "monotonic", fake)
    _reset()
    yield fake
    _reset()


def _install(monkeypatch, loader):
    monkeypatch.setattr(pricing_cache, "_load_db_nested", loader)
    return loader


def test_first_read_loads_and_caches(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(RATES))
    assert get_db_pricing_nested(TENANT) == RATES
    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.calls == 1


def test_within_ttl_serves_the_cached_copy(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)
    clock.advance(pricing_cache._TTL_SECONDS - 1)
    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.calls == 1


def test_expired_entry_reloads(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)
    clock.advance(pricing_cache._TTL_SECONDS + 1)
    assert get_db_pricing_nested(TENANT) == NEWER
    assert loader.calls == 2


def test_invalidation_reloads_immediately(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)
    invalidate_llm_cost_rates_cache(TENANT)
    assert get_db_pricing_nested(TENANT) == NEWER
    assert loader.calls == 2


def test_tenants_are_cached_independently(monkeypatch, clock):
    _install(monkeypatch, Loader(RATES, NEWER))
    assert get_db_pricing_nested(TENANT) == RATES
    assert get_db_pricing_nested("other") == NEWER
    assert get_db_pricing_nested(TENANT) == RATES


def test_db_failure_after_a_warm_load_serves_the_stale_copy(monkeypatch, clock):
    _install(monkeypatch, Loader(RATES, None))
    get_db_pricing_nested(TENANT)
    clock.advance(pricing_cache._TTL_SECONDS + 1)
    assert get_db_pricing_nested(TENANT) == RATES


def test_db_failure_on_a_cold_cache_recovers_once_the_cooldown_elapses(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(None, RATES))
    assert get_db_pricing_nested(TENANT) == {}
    clock.advance(pricing_cache._FAILURE_COOLDOWN_SECONDS + 1)
    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.calls == 2


def test_repeated_calls_during_an_outage_attempt_the_db_once_per_cooldown(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(None))
    get_db_pricing_nested(TENANT)
    assert loader.calls == 1

    for step in (0.1, 1, pricing_cache._FAILURE_COOLDOWN_SECONDS - 1.2):
        clock.advance(step)
        get_db_pricing_nested(TENANT)
    assert loader.calls == 1

    clock.advance(1)
    get_db_pricing_nested(TENANT)
    assert loader.calls == 2


def test_invalidation_bypasses_the_failure_cooldown(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(None, RATES))
    get_db_pricing_nested(TENANT)
    assert loader.calls == 1

    invalidate_llm_cost_rates_cache(TENANT)
    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.calls == 2


def _refresh_in_background():
    loaded: list = []
    thread = threading.Thread(target=lambda: loaded.append(get_db_pricing_nested(TENANT)))
    thread.start()
    return thread, loaded


def test_a_cold_stampede_reaches_the_db_once(monkeypatch, clock):
    loader = _install(monkeypatch, BlockingLoader(RATES))
    thread, loaded = _refresh_in_background()
    assert loader.entered.wait(5)

    assert [get_db_pricing_nested(TENANT) for _ in range(5)] == [{}] * 5
    assert loader.calls == 1

    loader.released.set()
    thread.join(5)
    assert loaded == [RATES]
    assert loader.calls == 1


def test_a_ttl_expiry_stampede_serves_the_stale_copy_while_one_caller_refreshes(monkeypatch, clock):
    loader = _install(monkeypatch, BlockingLoader(RATES, NEWER, block_on=2))
    get_db_pricing_nested(TENANT)
    clock.advance(pricing_cache._TTL_SECONDS + 1)

    thread, _ = _refresh_in_background()
    assert loader.entered.wait(5)

    assert [get_db_pricing_nested(TENANT) for _ in range(5)] == [RATES] * 5
    assert loader.calls == 2

    loader.released.set()
    thread.join(5)
    assert get_db_pricing_nested(TENANT) == NEWER


def test_a_crashing_load_does_not_wedge_the_tenant(monkeypatch, clock):

    def boom(tenant):
        raise RuntimeError("connection reset")

    _install(monkeypatch, boom)
    with pytest.raises(RuntimeError):
        get_db_pricing_nested(TENANT)
    assert TENANT not in pricing_cache._refreshing

    loader = _install(monkeypatch, Loader(RATES))
    clock.advance(pricing_cache._FAILURE_COOLDOWN_SECONDS + 1)
    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.calls == 1
