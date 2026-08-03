"""Route-level tests for the Run-all Redis lock: contention → 409, ownership-safe
release (compare-and-delete with the token we acquired), and a release failure that
must not mask a successful response."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import test_evaluations as route_mod


def _fake_redis(*, acquired: bool = True, release_error: bool = False):
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True if acquired else None)
    if release_error:
        redis.eval = AsyncMock(side_effect=RuntimeError("redis down"))
    else:
        redis.eval = AsyncMock(return_value=1)
    return redis


def _patch_injector(monkeypatch, redis):
    fake_injector = MagicMock()
    fake_injector.get.return_value = redis
    monkeypatch.setattr(route_mod, "injector", fake_injector)


def _service(*, active: bool = False, started=None):
    service = AsyncMock()
    service.workflow_has_active_run = AsyncMock(return_value=active)
    service.start_workflow_evaluations = AsyncMock(return_value=started or [])
    return service


@pytest.mark.asyncio
async def test_lock_contention_returns_409_without_starting(monkeypatch):
    """If the lock is already held (SET NX fails), refuse and never start a batch
    or touch the lock (nothing to release — we did not acquire it)."""
    redis = _fake_redis(acquired=False)
    _patch_injector(monkeypatch, redis)
    service = _service()

    with pytest.raises(HTTPException) as exc:
        await route_mod.run_workflow_evaluations(uuid4(), service)

    assert exc.value.status_code == 409
    service.start_workflow_evaluations.assert_not_awaited()
    redis.eval.assert_not_awaited()  # never acquired → never released


@pytest.mark.asyncio
async def test_already_running_returns_409_and_releases_own_lock(monkeypatch):
    """Lock acquired but a batch is already running → 409, and we release using a
    compare-and-delete against the exact token we set (ownership-safe)."""
    redis = _fake_redis(acquired=True)
    _patch_injector(monkeypatch, redis)
    service = _service(active=True)

    with pytest.raises(HTTPException) as exc:
        await route_mod.run_workflow_evaluations(uuid4(), service)

    assert exc.value.status_code == 409
    service.start_workflow_evaluations.assert_not_awaited()

    set_key, set_token = redis.set.await_args.args
    redis.eval.assert_awaited_once()
    script, numkeys, eval_key, eval_token = redis.eval.await_args.args
    assert script == route_mod._RELEASE_LOCK_LUA
    assert numkeys == 1
    assert eval_key == set_key  # same lock key
    assert eval_token == set_token  # release only our own token


@pytest.mark.asyncio
async def test_happy_path_starts_then_releases(monkeypatch):
    redis = _fake_redis(acquired=True)
    _patch_injector(monkeypatch, redis)
    started = [SimpleNamespace(evaluation_id=uuid4())]
    service = _service(active=False, started=started)

    result = await route_mod.run_workflow_evaluations(uuid4(), service)

    assert result is started
    service.start_workflow_evaluations.assert_awaited_once()
    redis.eval.assert_awaited_once()  # released after starting


@pytest.mark.asyncio
async def test_release_failure_does_not_mask_response(monkeypatch):
    """A Redis error while releasing must be swallowed, not turned into a 500."""
    redis = _fake_redis(acquired=True, release_error=True)
    _patch_injector(monkeypatch, redis)
    started = [SimpleNamespace(evaluation_id=uuid4())]
    service = _service(active=False, started=started)

    result = await route_mod.run_workflow_evaluations(uuid4(), service)

    assert result is started  # successful start still returned despite release error
