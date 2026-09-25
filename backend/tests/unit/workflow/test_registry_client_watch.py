"""Unit tests for noticing an HTTP client that left while its agent turn was queued"""

import asyncio

import pytest

from app.modules.workflow.registry import HttpClientWatch


class FakeRequest:
    def __init__(self, body_consumed=True, disconnects=False):
        self._stream_consumed = body_consumed
        self._disconnects = disconnects

    async def receive(self):
        if self._disconnects:
            return {"type": "http.disconnect"}
        await asyncio.Event().wait()  # a connected client never sends anything more


@pytest.mark.asyncio
async def test_client_that_left_is_reported_gone():
    watch = HttpClientWatch(FakeRequest(disconnects=True))
    watch.start()
    await asyncio.sleep(0)

    assert await watch.client_gone() is True


@pytest.mark.asyncio
async def test_connected_client_is_not_gone_and_listener_is_cancelled():
    watch = HttpClientWatch(FakeRequest())
    watch.start()
    listener = watch._task

    assert await watch.client_gone() is False
    await asyncio.sleep(0)
    assert listener.cancelled()


@pytest.mark.asyncio
async def test_no_listener_without_a_request_or_with_an_unread_body():
    # Outside a request there is no HTTP request in the context, so None stays None.
    for request in (None, FakeRequest(body_consumed=False)):
        watch = HttpClientWatch(request)
        watch.start()

        assert watch._task is None
        assert await watch.client_gone() is False


@pytest.mark.asyncio
async def test_stop_cancels_a_pending_listener():
    watch = HttpClientWatch(FakeRequest())
    watch.start()
    listener = watch._task

    watch.stop()
    await asyncio.sleep(0)

    assert listener.cancelled()
    assert watch._task is None
