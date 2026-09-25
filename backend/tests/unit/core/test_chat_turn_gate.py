"""Unit tests for the agent-turn admission gate"""

import asyncio

import pytest

from app.core.chat_turn_gate import ChatTurnGate
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


async def _hold_slot(gate: ChatTurnGate, release: asyncio.Event, entered: asyncio.Event):
    async with gate.slot(context="test"):
        entered.set()
        await release.wait()


async def _let_tasks_run():
    await asyncio.sleep(0.01)


async def _expect_rejection_while_one_turn_holds_the_place(gate: ChatTurnGate, before_wait=None):
    release = asyncio.Event()
    holder = asyncio.create_task(_hold_slot(gate, release, asyncio.Event()))
    await _let_tasks_run()

    with pytest.raises(AppException) as raised:
        async with gate.slot(context="test", before_wait=before_wait):
            pass

    release.set()
    await holder
    return raised.value


@pytest.mark.asyncio
async def test_runs_up_to_max_inflight_and_queues_the_rest():
    gate = ChatTurnGate(max_inflight=2, queue_timeout_seconds=1.0)
    release = asyncio.Event()
    entered = [asyncio.Event() for _ in range(3)]

    tasks = [asyncio.create_task(_hold_slot(gate, release, flag)) for flag in entered]
    await _let_tasks_run()

    assert entered[0].is_set() and entered[1].is_set()
    assert not entered[2].is_set()

    release.set()
    await asyncio.gather(*tasks)
    assert entered[2].is_set()


@pytest.mark.asyncio
async def test_rejects_with_503_when_the_wait_runs_out():
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=0.05)

    rejection = await _expect_rejection_while_one_turn_holds_the_place(gate)

    assert rejection.status_code == 503
    assert rejection.error_key == ErrorKey.CHAT_TURN_CAPACITY_EXCEEDED


@pytest.mark.asyncio
async def test_before_wait_runs_only_when_the_turn_has_to_queue():
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=0.05)
    calls = []

    async def before_wait():
        calls.append("released")

    async with gate.slot(context="test", before_wait=before_wait):
        pass
    assert calls == []

    await _expect_rejection_while_one_turn_holds_the_place(gate, before_wait=before_wait)
    assert calls == ["released"]


@pytest.mark.asyncio
async def test_place_is_returned_when_the_turn_fails():
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=0.05)

    with pytest.raises(RuntimeError):
        async with gate.slot(context="test"):
            raise RuntimeError("agent failed")

    # The only place must be free again, otherwise this would be rejected after the timeout.
    async with gate.slot(context="test"):
        pass


async def _enter_slot(gate: ChatTurnGate, caller_gone):
    async with gate.slot(context="test", caller_gone=caller_gone):
        pass


@pytest.mark.asyncio
async def test_queued_turn_is_skipped_when_its_caller_has_gone():
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=1.0)
    release = asyncio.Event()
    holder = asyncio.create_task(_hold_slot(gate, release, asyncio.Event()))
    await _let_tasks_run()

    async def caller_gone():
        return True

    abandoned = asyncio.create_task(_enter_slot(gate, caller_gone))
    await _let_tasks_run()
    release.set()
    await holder

    with pytest.raises(AppException) as raised:
        await abandoned
    assert raised.value.error_key == ErrorKey.CHAT_TURN_CLIENT_DISCONNECTED

    # The place was given straight back, otherwise this would be rejected after the timeout.
    async with gate.slot(context="test"):
        pass


@pytest.mark.asyncio
async def test_caller_gone_is_not_consulted_when_the_turn_did_not_queue():
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=0.05)
    calls = []

    async def caller_gone():
        calls.append("asked")
        return True

    async with gate.slot(context="test", caller_gone=caller_gone):
        pass
    assert calls == []


@pytest.mark.asyncio
async def test_disabled_gate_never_waits():
    gate = ChatTurnGate(max_inflight=0, queue_timeout_seconds=0.05)
    release = asyncio.Event()
    entered = [asyncio.Event() for _ in range(5)]

    tasks = [asyncio.create_task(_hold_slot(gate, release, flag)) for flag in entered]
    await _let_tasks_run()

    assert all(flag.is_set() for flag in entered)
    release.set()
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_zero_timeout_admits_free_places_and_rejects_only_when_full():
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=0)

    async with gate.slot(context="test"):
        pass

    rejection = await _expect_rejection_while_one_turn_holds_the_place(gate)
    assert rejection.status_code == 503


def test_gate_keeps_working_across_event_loops():
    gate = ChatTurnGate(max_inflight=1, queue_timeout_seconds=0.05)

    first = asyncio.run(_expect_rejection_while_one_turn_holds_the_place(gate))
    second = asyncio.run(_expect_rejection_while_one_turn_holds_the_place(gate))

    assert first.status_code == second.status_code == 503
