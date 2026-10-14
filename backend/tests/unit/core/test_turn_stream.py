"""Unit tests for the server-sent event stream of one chat turn"""

import logging

import pytest

from app.core import turn_stream
from app.core.turn_stream import TurnStream, current_stream


@pytest.mark.asyncio
async def test_frames_arrive_in_order_and_close_ends_the_stream():
    stream = TurnStream("c1")
    stream.emit("activity", kind="tool", phase="start")
    stream.emit("done", conversation={"id": "c1"})
    stream.close()

    assert [frame async for frame in stream.frames()] == [
        'event: activity\ndata: {"kind": "tool", "phase": "start"}\n\n',
        'event: done\ndata: {"conversation": {"id": "c1"}}\n\n',
    ]


@pytest.mark.asyncio
async def test_silence_sends_a_keepalive_comment(monkeypatch):
    monkeypatch.setattr(turn_stream, "KEEPALIVE_SECONDS", 0.01)
    stream = TurnStream("c1")
    frames = stream.frames()

    assert await frames.__anext__() == ": ping\n\n"
    stream.close()
    assert [frame async for frame in frames] == []


def test_activity_reaches_only_the_current_stream():
    stream = TurnStream("c1")
    turn_stream.emit_activity("tool", "start")

    token = current_stream.set(stream)
    try:
        turn_stream.emit_activity("knowledge", "start")
    finally:
        current_stream.reset(token)

    assert stream.queue.qsize() == 1
    assert stream.queue.get_nowait() == 'event: activity\ndata: {"kind": "knowledge", "phase": "start"}\n\n'


def test_first_activity_is_logged_once(caplog):
    stream = TurnStream("c1")
    with caplog.at_level(logging.INFO, logger="app.core.turn_stream"):
        stream.emit("activity", kind="tool", phase="start")
        stream.emit("activity", kind="tool", phase="end")
        stream.emit("done", conversation={})

    assert [record.getMessage().split(" after ")[0] for record in caplog.records] == ["First activity"]
