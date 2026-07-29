"""Unit tests for the application-owned background task registry"""

import asyncio

import pytest

from app.core.tenant_scope import get_tenant_context, set_tenant_context
from app.core.utils import background_tasks
from app.core.utils.background_tasks import drain, spawn


@pytest.fixture(autouse=True)
def _empty_registry():
    background_tasks._TASKS.clear()
    yield
    background_tasks._TASKS.clear()


class TestSpawn:
    @pytest.mark.asyncio
    async def test_registers_then_discards_on_completion(self):
        async def work():
            return None

        task = spawn(work(), name="probe")
        assert task in background_tasks._TASKS

        await task
        await asyncio.sleep(0)
        assert task not in background_tasks._TASKS

    @pytest.mark.asyncio
    async def test_task_exception_is_retrieved_and_logged(self, caplog):
        async def boom():
            raise RuntimeError("capture exploded")

        with caplog.at_level("WARNING"):
            task = spawn(boom(), name="boom")
            await asyncio.gather(task, return_exceptions=True)
            await asyncio.sleep(0)

        assert "boom" in caplog.text
        assert "capture exploded" in caplog.text

    @pytest.mark.asyncio
    async def test_closes_the_coroutine_when_scheduling_fails(self, monkeypatch, recwarn):
        async def work():
            return None

        coro = work()
        monkeypatch.setattr(
            background_tasks.asyncio, "create_task", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no loop"))
        )

        with pytest.raises(RuntimeError):
            spawn(coro, name="doomed")

        assert not background_tasks._TASKS
        assert coro.cr_frame is None
        del coro
        assert not [w for w in recwarn.list if "never awaited" in str(w.message)]

    @pytest.mark.asyncio
    async def test_runs_in_a_copy_of_the_spawning_tenant_context(self):
        observed = []

        async def probe():
            await asyncio.sleep(0)
            observed.append(get_tenant_context())

        set_tenant_context("tenant-a")
        task = spawn(probe(), name="tenant-probe")
        set_tenant_context("tenant-b")
        await task

        assert observed == ["tenant-a"]


class TestDrain:
    @pytest.mark.asyncio
    async def test_no_op_when_nothing_is_pending(self):
        await drain(timeout=0.01)

    @pytest.mark.asyncio
    async def test_waits_for_tasks_to_finish(self):
        finished = []

        async def work():
            await asyncio.sleep(0.01)
            finished.append(True)

        spawn(work(), name="slow")
        await drain(timeout=5.0)

        assert finished == [True]

    @pytest.mark.asyncio
    async def test_stragglers_are_cancelled_and_awaited_before_returning(self):
        cleaned = []

        async def hangs():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                await asyncio.sleep(0)
                cleaned.append(True)
                raise

        task = spawn(hangs(), name="hangs")
        await drain(timeout=0.01)

        assert task.done()
        assert cleaned == [True]
