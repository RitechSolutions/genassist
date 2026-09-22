"""Regression test for conversation memory cache cleanup: it must delete the known
per-conversation Redis keys directly, never SCAN the keyspace for them. A SCAN
walks the entire keyspace per call regardless of match count, which made cleanup
cost grow with total Redis keys instead of staying constant."""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.cache.redis_cache as redis_cache_mod
import app.core.tenant_scope as tenant_scope_mod
import app.dependencies.injector as injector_mod


def _patch_redis(monkeypatch):
    redis = AsyncMock()
    redis.delete = AsyncMock(return_value=4)
    fake_injector = MagicMock()
    fake_injector.get.return_value = redis
    monkeypatch.setattr(injector_mod, "injector", fake_injector)
    return redis


def _patch_tenant(monkeypatch, tenant_id: str | None):
    monkeypatch.setattr(tenant_scope_mod, "get_tenant_context", lambda: tenant_id)


@pytest.mark.asyncio
async def test_clear_conversation_memory_cache_deletes_known_keys_without_scanning(monkeypatch):
    redis = _patch_redis(monkeypatch)
    _patch_tenant(monkeypatch, "acme")
    conversation_id = uuid4()

    await redis_cache_mod.clear_conversation_memory_cache(conversation_id)

    assert not hasattr(redis, "scan_iter") or not redis.scan_iter.called
    redis.delete.assert_awaited_once()
    deleted_keys = redis.delete.await_args.args
    assert set(deleted_keys) == {
        f"tenant:acme::conversation:{conversation_id}:info",
        f"tenant:acme::conversation:{conversation_id}:messages",
        f"tenant:acme::conversation:{conversation_id}:metadata",
        f"tenant:acme::conversation:{conversation_id}:stateful",
    }


@pytest.mark.asyncio
async def test_clear_conversation_memory_cache_without_tenant_context(monkeypatch):
    redis = _patch_redis(monkeypatch)
    _patch_tenant(monkeypatch, None)
    conversation_id = uuid4()

    await redis_cache_mod.clear_conversation_memory_cache(conversation_id)

    deleted_keys = redis.delete.await_args.args
    assert set(deleted_keys) == {
        f":conversation:{conversation_id}:info",
        f":conversation:{conversation_id}:messages",
        f":conversation:{conversation_id}:metadata",
        f":conversation:{conversation_id}:stateful",
    }


@pytest.mark.asyncio
async def test_clear_conversation_memory_cache_swallows_redis_errors(monkeypatch):
    redis = _patch_redis(monkeypatch)
    _patch_tenant(monkeypatch, "acme")
    redis.delete = AsyncMock(side_effect=RuntimeError("redis down"))

    # Must not raise: cache cleanup failures shouldn't break the caller's flow.
    await redis_cache_mod.clear_conversation_memory_cache(uuid4())
