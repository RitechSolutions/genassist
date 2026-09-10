"""Each Celery task runs on a fresh event loop; pooled async Redis connections must not outlive it."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks import base


def _client(disconnect_error=None):
    client = MagicMock()
    client.connection_pool.disconnect = AsyncMock(side_effect=disconnect_error)
    return client


class TestDisconnectAsyncRedisPools:
    @pytest.mark.asyncio
    async def test_every_process_wide_client_is_disconnected(self):
        clients = [_client(), _client(), _client()]
        with patch.object(base, "_async_redis_clients", return_value=clients):
            await base.disconnect_async_redis_pools()

        for client in clients:
            client.connection_pool.disconnect.assert_awaited_once_with(inuse_connections=True)

    @pytest.mark.asyncio
    async def test_a_failing_client_does_not_stop_the_others_or_the_task(self):
        broken, healthy = _client(RuntimeError("gone")), _client()
        with patch.object(base, "_async_redis_clients", return_value=[broken, healthy]):
            await base.disconnect_async_redis_pools()

        healthy.connection_pool.disconnect.assert_awaited_once()


class TestRunAsyncInCelery:
    def test_pools_are_dropped_after_a_successful_task(self):
        async def work():
            return "done"

        with patch.object(base, "disconnect_async_redis_pools", AsyncMock()) as drop:
            assert base.run_async_in_celery(work()) == "done"

        drop.assert_awaited_once()

    def test_pools_are_dropped_after_a_failing_task(self):
        async def work():
            raise ValueError("boom")

        with patch.object(base, "disconnect_async_redis_pools", AsyncMock()) as drop:
            with pytest.raises(ValueError):
                base.run_async_in_celery(work())

        drop.assert_awaited_once()

    def test_pools_are_dropped_after_a_timeout(self):
        async def work():
            await asyncio.sleep(5)

        with patch.object(base, "disconnect_async_redis_pools", AsyncMock()) as drop:
            with pytest.raises(asyncio.TimeoutError):
                base.run_async_in_celery(work(), timeout=0.01)

        drop.assert_awaited_once()

    def test_the_drop_runs_inside_the_task_loop(self):
        """The disconnect needs the same loop the connections belong to."""
        seen = {}

        async def record_loop():
            seen["drop"] = asyncio.get_running_loop()

        async def work():
            seen["task"] = asyncio.get_running_loop()

        with patch.object(base, "disconnect_async_redis_pools", record_loop):
            base.run_async_in_celery(work())

        assert seen["drop"] is seen["task"]
