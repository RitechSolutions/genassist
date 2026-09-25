"""Sizing of the event loop's default executor, where synchronous model clients run."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

THREAD_NAME_PREFIX = "model-call"


def configure_default_executor(loop: asyncio.AbstractEventLoop, thread_count: int) -> None:
    """Install a fixed-size default executor on the loop. Zero or less keeps Python's default."""
    if thread_count <= 0:
        return

    executor = ThreadPoolExecutor(
        max_workers=thread_count, thread_name_prefix=THREAD_NAME_PREFIX
    )
    loop.set_default_executor(executor)
