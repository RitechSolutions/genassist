"""Unit tests for sizing the event loop's default executor"""

import asyncio
import threading

import pytest

from app.core.concurrency import THREAD_NAME_PREFIX, configure_default_executor


def _current_thread_name() -> str:
    return threading.current_thread().name


@pytest.mark.asyncio
async def test_jobs_on_the_default_executor_run_on_the_sized_pool():
    loop = asyncio.get_running_loop()
    configure_default_executor(loop, 3)

    thread_name = await loop.run_in_executor(None, _current_thread_name)

    assert thread_name.startswith(THREAD_NAME_PREFIX)


@pytest.mark.asyncio
@pytest.mark.parametrize("thread_count", [0, -1])
async def test_non_positive_count_keeps_pythons_default(thread_count):
    loop = asyncio.get_running_loop()
    configure_default_executor(loop, thread_count)

    thread_name = await loop.run_in_executor(None, _current_thread_name)

    assert not thread_name.startswith(THREAD_NAME_PREFIX)
