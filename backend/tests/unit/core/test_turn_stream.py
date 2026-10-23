"""Unit tests for the server-sent event stream of one chat turn"""

import logging
from contextlib import contextmanager

import pytest

from app.core import turn_stream
from app.core.turn_stream import TurnStream, current_stream, node_path


@contextmanager
def _running(*node_ids):
    token = node_path.set(node_ids)
    try:
        yield
    finally:
        node_path.reset(token)


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


def test_reply_text_streams_while_envelopes_stay_muted():
    stream = TurnStream("c1")
    stream.delta("n1", "reply", "  ")
    stream.delta("n1", "reply", "Hello")
    stream.delta("n1", "envelope", ' {"message"')
    stream.delta("n1", "reply", " there")
    stream.delta("n1", "fence", "`")
    stream.delta("n1", "fence", "``json")
    stream.delta("n1", "envelope", ': "hi"}')

    frames = [stream.queue.get_nowait() for _ in range(stream.queue.qsize())]
    assert frames == [
        'event: delta\ndata: {"call_id": "reply", "text": "Hello"}\n\n',
        'event: delta\ndata: {"call_id": "reply", "text": " there"}\n\n',
    ]


def test_text_a_tool_start_cleared_does_not_hold_off_later_activity():
    stream = TurnStream("c1")
    stream.delta("n1", "scratch", "Let me check")
    with _running("n1", "tool"):
        stream.activity("tool", "start")
    stream.end_reply("n1")
    stream.activity("knowledge", "start")

    assert [stream.queue.get_nowait() for _ in range(stream.queue.qsize())] == [
        'event: delta\ndata: {"call_id": "scratch", "text": "Let me check"}\n\n',
        'event: activity\ndata: {"kind": "tool", "phase": "start"}\n\n',
        'event: activity\ndata: {"kind": "knowledge", "phase": "start"}\n\n',
    ]


def test_a_final_reply_holds_off_activity_starts_until_new_text_streams():
    stream = TurnStream("c1")
    token = current_stream.set(stream)
    try:
        stream.delta("n1", "answer", "Done")
        turn_stream.end_reply("n1")
        turn_stream.emit_activity("tool", "start")
        turn_stream.emit_activity("knowledge", "end")
        stream.delta("n1", "next", "More")
        with _running("n1", "tool"):
            turn_stream.emit_activity("tool", "start")
    finally:
        current_stream.reset(token)

    assert [stream.queue.get_nowait() for _ in range(stream.queue.qsize())] == [
        'event: delta\ndata: {"call_id": "answer", "text": "Done"}\n\n',
        'event: activity\ndata: {"kind": "knowledge", "phase": "end"}\n\n',
        'event: delta\ndata: {"call_id": "next", "text": "More"}\n\n',
        'event: activity\ndata: {"kind": "tool", "phase": "start"}\n\n',
    ]


def test_a_second_node_cannot_interleave_with_the_reply_in_progress():
    stream = TurnStream("c1")
    stream.delta("a", "call-a", "Hello")
    stream.delta("b", "call-b", "Other")
    stream.end_reply("b")
    with _running("a", "tool"):
        stream.activity("tool", "start")
    stream.delta("a", "call-a", " there")
    stream.end_reply("a")
    stream.delta("b", "call-b", " late")
    stream.delta("b", "call-c", "Next")

    assert [stream.queue.get_nowait() for _ in range(stream.queue.qsize())] == [
        'event: delta\ndata: {"call_id": "call-a", "text": "Hello"}\n\n',
        'event: activity\ndata: {"kind": "tool", "phase": "start"}\n\n',
        'event: delta\ndata: {"call_id": "call-a", "text": " there"}\n\n',
        'event: delta\ndata: {"call_id": "call-c", "text": "Next"}\n\n',
    ]
