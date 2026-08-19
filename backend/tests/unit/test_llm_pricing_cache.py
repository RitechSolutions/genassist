"""Unit tests for the per-tenant rate cache: TTL refresh, invalidation and DB-failure behaviour"""

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


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(pricing_cache.time, "monotonic", fake)
    invalidate_llm_cost_rates_cache()
    yield fake
    invalidate_llm_cost_rates_cache()


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


def test_db_failure_on_a_cold_cache_prices_from_the_bundled_table(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(None, RATES))
    assert get_db_pricing_nested(TENANT) == {}
    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.calls == 2
