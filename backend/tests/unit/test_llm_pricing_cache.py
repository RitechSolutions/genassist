import threading

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import app.services.llm_pricing_cache as pricing_cache
from app.services.llm_pricing_cache import (
    get_db_pricing_nested,
    invalidate_llm_cost_rates_cache,
    invalidate_llm_cost_rates_cache_after_commit,
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


def _wait_for_background_refresh(timeout: float = 5.0):
    import time as real_time

    for _ in range(int(timeout / 0.01)):
        with pricing_cache._condition:
            if not pricing_cache._refreshing:
                return
        real_time.sleep(0.01)
    raise AssertionError("the background refresh never finished")


def test_expired_entry_serves_stale_and_refreshes_in_the_background(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)
    clock.advance(pricing_cache._TTL_SECONDS + 1)

    assert get_db_pricing_nested(TENANT) == RATES

    _wait_for_background_refresh()
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
    _wait_for_background_refresh()
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


def test_a_cold_stampede_reaches_the_db_once_and_every_caller_waits_for_it(monkeypatch, clock):
    loader = _install(monkeypatch, BlockingLoader(RATES))
    thread, loaded = _refresh_in_background()
    assert loader.entered.wait(5)

    waiters = [_refresh_in_background() for _ in range(3)]
    loader.released.set()
    thread.join(5)
    for waiter_thread, _ in waiters:
        waiter_thread.join(5)

    assert loaded == [RATES]
    assert [result for _, results in waiters for result in results] == [RATES] * 3
    assert loader.calls == 1


def test_a_failed_thread_start_releases_the_refresh_slot(monkeypatch, clock):
    loader = _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)
    clock.advance(pricing_cache._TTL_SECONDS + 1)

    class _Unstartable:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")

    real_thread = threading.Thread
    monkeypatch.setattr(pricing_cache.threading, "Thread", _Unstartable)
    assert get_db_pricing_nested(TENANT) == RATES
    assert TENANT not in pricing_cache._refreshing

    monkeypatch.setattr(pricing_cache.threading, "Thread", real_thread)
    assert get_db_pricing_nested(TENANT) == RATES
    _wait_for_background_refresh()
    assert get_db_pricing_nested(TENANT) == NEWER
    assert loader.calls == 2


def test_a_ttl_expiry_stampede_serves_the_stale_copy_while_one_refresh_runs(monkeypatch, clock):
    loader = _install(monkeypatch, BlockingLoader(RATES, NEWER, block_on=2))
    get_db_pricing_nested(TENANT)
    clock.advance(pricing_cache._TTL_SECONDS + 1)

    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.entered.wait(5)

    assert [get_db_pricing_nested(TENANT) for _ in range(5)] == [RATES] * 5
    assert loader.calls == 2

    loader.released.set()
    _wait_for_background_refresh()
    assert get_db_pricing_nested(TENANT) == NEWER


@pytest.mark.parametrize("scope", ["tenant", "all"], ids=["one-tenant", "all-tenants"])
def test_an_invalidation_during_a_load_discards_the_stale_snapshot(monkeypatch, clock, scope):
    loader = _install(monkeypatch, BlockingLoader(RATES, NEWER))
    thread, loaded = _refresh_in_background()
    assert loader.entered.wait(5)

    invalidate_llm_cost_rates_cache(TENANT if scope == "tenant" else None)
    loader.released.set()
    thread.join(5)

    assert loaded == [NEWER]
    assert loader.calls == 2
    assert get_db_pricing_nested(TENANT) == NEWER


def test_an_invalidation_during_a_failing_load_does_not_resurrect_the_cooldown(monkeypatch, clock):
    loader = _install(monkeypatch, BlockingLoader(None, RATES))
    thread, loaded = _refresh_in_background()
    assert loader.entered.wait(5)

    invalidate_llm_cost_rates_cache(TENANT)
    loader.released.set()
    thread.join(5)

    assert loaded == [RATES]
    assert loader.calls == 2


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


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    with Session(engine) as real_session:
        real_session.execute(text("SELECT 1"))
        yield real_session
    engine.dispose()


def test_a_pending_invalidation_leaves_the_cache_warm_until_the_commit(monkeypatch, clock, session):
    loader = _install(monkeypatch, Loader(RATES, NEWER))
    assert get_db_pricing_nested(TENANT) == RATES

    invalidate_llm_cost_rates_cache_after_commit(session, TENANT)
    assert get_db_pricing_nested(TENANT) == RATES, "uncommitted writes must not be published"

    session.commit()
    assert get_db_pricing_nested(TENANT) == NEWER
    assert loader.calls == 2


def test_a_rollback_keeps_the_committed_rates_cached(monkeypatch, clock, session):
    loader = _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)

    invalidate_llm_cost_rates_cache_after_commit(session, TENANT)
    session.rollback()
    session.commit()

    assert get_db_pricing_nested(TENANT) == RATES
    assert loader.calls == 1


def test_a_released_savepoint_does_not_publish_the_write_early(monkeypatch, clock, session):
    _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)

    invalidate_llm_cost_rates_cache_after_commit(session, TENANT)
    with session.begin_nested():
        session.execute(text("SELECT 1"))

    assert pricing_cache._cache.get(TENANT) is not None, "a savepoint is not the outer commit"
    session.commit()
    assert TENANT not in pricing_cache._cache


def test_a_savepoint_rollback_keeps_the_invalidation_for_the_outer_commit(monkeypatch, clock, session):
    _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)

    invalidate_llm_cost_rates_cache_after_commit(session, TENANT)
    with pytest.raises(RuntimeError):
        with session.begin_nested():
            session.execute(text("SELECT 1"))
            raise RuntimeError("the inner unit of work failed")

    session.commit()
    assert TENANT not in pricing_cache._cache, "the outer commit must still publish the write"


def test_committing_one_tenant_leaves_the_others_cached(monkeypatch, clock, session):
    other = "globex"
    _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)
    get_db_pricing_nested(other)

    invalidate_llm_cost_rates_cache_after_commit(session, TENANT)
    session.commit()

    assert pricing_cache._cache.get(other) is not None, "another tenant's entry survives"
    assert TENANT not in pricing_cache._cache


def test_a_commit_drains_the_queue_once(monkeypatch, clock, session):
    _install(monkeypatch, Loader(RATES, NEWER))
    get_db_pricing_nested(TENANT)

    invalidate_llm_cost_rates_cache_after_commit(session, TENANT)
    session.commit()
    get_db_pricing_nested(TENANT)
    session.commit()

    assert pricing_cache._cache.get(TENANT) is not None, "a later commit must not re-clear"

