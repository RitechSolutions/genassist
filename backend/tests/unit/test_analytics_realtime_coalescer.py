"""Unit tests for the per-process coalescing of real-time analytics events"""

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.core.tenant_scope import get_tenant_context, set_tenant_context
from app.core.utils import background_tasks
from app.services import analytics_realtime as ar

AGENT_ID = uuid4()


def _reply(response_ms, nodes=(), input_tokens=10):
    return {
        "agent_id": str(AGENT_ID),
        "status": "success",
        "token_usage": {"input_tokens": input_tokens, "output_tokens": 20},
        "cost_usd": 0.001,
        "row_agent_response": {
            "performance_metrics": {"totalExecutionTime": response_ms},
            "state": {"nodeExecutionStatus": {f"n{i}": node for i, node in enumerate(nodes)}},
        },
    }


@pytest.fixture(autouse=True)
def _empty_state():
    ar._pending.clear()
    ar._flushers.clear()
    background_tasks._TASKS.clear()
    yield
    ar._pending.clear()
    ar._flushers.clear()
    background_tasks._TASKS.clear()


@pytest.fixture
def writes(monkeypatch):
    seen = []

    async def record(agent_id, stat_date, delta):
        seen.append((get_tenant_context(), agent_id, stat_date, delta))

    monkeypatch.setattr(ar, "_write", record)
    return seen


@pytest.mark.asyncio
async def test_events_merged_during_a_flush_go_out_in_one_more_write(monkeypatch):
    gate = asyncio.Event()
    seen = []
    writes_in_flight = {"now": 0, "peak": 0}

    async def slow_write(agent_id, stat_date, delta):
        writes_in_flight["now"] += 1
        writes_in_flight["peak"] = max(writes_in_flight["peak"], writes_in_flight["now"])
        seen.append(delta.events)
        if len(seen) == 1:
            await gate.wait()
        writes_in_flight["now"] -= 1

    monkeypatch.setattr(ar, "_write", slow_write)
    await ar.update_stats_incrementally(_reply(100))
    await asyncio.sleep(0)
    for _ in range(4):
        await ar.update_stats_incrementally(_reply(100))
    await ar.update_conversation_started(AGENT_ID)
    await asyncio.sleep(0)
    gate.set()
    await background_tasks.drain(timeout=5.0)

    assert seen == [1, 5]
    assert writes_in_flight["peak"] == 1
    assert ar._pending == {} and ar._flushers == {}


@pytest.mark.asyncio
async def test_merge_sums_counts_and_keeps_extremes_per_node_type(writes, monkeypatch):
    async def lookup(conversation_id):
        return AGENT_ID

    monkeypatch.setattr(ar, "_agent_id_for", lookup)
    llm_ok = {"type": "llm", "status": "success", "time_taken": 50}
    llm_failed = {"type": "llm", "status": "failed", "time_taken": 20}
    tool_untimed = {"type": "tool", "status": "success"}
    await ar.update_stats_incrementally(_reply(300, [llm_ok, tool_untimed]))
    await ar.update_stats_incrementally(_reply(100, [llm_failed], input_tokens=5))
    await ar.update_conversation_started(AGENT_ID)
    await ar.update_conversation_finalized(uuid4())
    await ar.update_feedback_given(uuid4(), True)
    await ar.update_feedback_given(uuid4(), False)
    await background_tasks.drain(timeout=5.0)

    [(_, _, _, delta)] = writes
    assert (delta.events, delta.executions, delta.successes) == (6, 2, 2)
    assert (delta.timed, delta.total_ms, delta.min_ms, delta.max_ms) == (2, 400.0, 100.0, 300.0)
    assert (delta.nodes_executed, delta.rated, delta.success_rate_sum) == (3, 2, 1.0)
    assert (delta.input_tokens, delta.output_tokens) == (15, 40)
    assert (delta.starts, delta.finalizes, delta.thumbs_up, delta.thumbs_down) == (1, 1, 1, 1)
    llm, tool = delta.nodes["llm"], delta.nodes["tool"]
    assert (llm.executions, llm.successes, llm.min_ms, llm.max_ms, llm.total_ms) == (2, 1, 20.0, 50.0, 70.0)
    assert (tool.executions, tool.timed) == (1, 0)


@pytest.mark.asyncio
async def test_a_failed_flush_is_retried_once_with_newer_events_and_logs_no_warning(monkeypatch, caplog):
    gate = asyncio.Event()
    seen = []

    async def fail_first(agent_id, stat_date, delta):
        seen.append(delta.events)
        if len(seen) == 1:
            await gate.wait()
            raise RuntimeError("lock timeout")

    monkeypatch.setattr(ar, "_write", fail_first)
    await ar.update_stats_incrementally(_reply(100))
    await asyncio.sleep(0)
    await ar.update_stats_incrementally(_reply(100))
    await ar.update_stats_incrementally(_reply(100))
    with caplog.at_level("WARNING", logger=ar.__name__):
        gate.set()
        await background_tasks.drain(timeout=5.0)

    assert seen == [1, 3]
    assert caplog.records == []


@pytest.mark.asyncio
async def test_a_flush_failing_twice_drops_its_events_and_releases_the_key(monkeypatch, caplog):
    seen = []

    async def always_fails(agent_id, stat_date, delta):
        seen.append(delta.events)
        raise RuntimeError("db down")

    monkeypatch.setattr(ar, "_write", always_fails)
    for _ in range(3):
        await ar.update_stats_incrementally(_reply(100))
    with caplog.at_level("WARNING", logger=ar.__name__):
        await background_tasks.drain(timeout=5.0)

    assert seen == [3, 3]
    assert "dropped 3 event(s)" in caplog.text
    assert ar._flushers == {}

    await ar.update_stats_incrementally(_reply(100))
    await background_tasks.drain(timeout=5.0)
    assert seen == [3, 3, 1, 1]


@pytest.mark.asyncio
async def test_each_tenant_flushes_its_own_bucket(writes):
    set_tenant_context("tenant-a")
    await ar.update_conversation_started(AGENT_ID)
    set_tenant_context("tenant-b")
    await ar.update_conversation_started(AGENT_ID)
    await background_tasks.drain(timeout=5.0)

    assert sorted((tenant, delta.starts) for tenant, _, _, delta in writes) == [("tenant-a", 1), ("tenant-b", 1)]


@pytest.mark.asyncio
async def test_a_finalize_books_on_the_day_it_happened_even_if_the_lookup_crosses_midnight(writes, monkeypatch):
    clock = [datetime(2026, 7, 1, 23, 59, 59, tzinfo=timezone.utc)]

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    async def slow_lookup(conversation_id):
        clock[0] = datetime(2026, 7, 2, 0, 0, 1, tzinfo=timezone.utc)
        return AGENT_ID

    monkeypatch.setattr(ar, "datetime", FrozenDatetime)
    monkeypatch.setattr(ar, "_agent_id_for", slow_lookup)
    await ar.update_conversation_finalized(uuid4())
    await background_tasks.drain(timeout=5.0)

    assert [(stat_date, delta.finalizes) for _, _, stat_date, delta in writes] == [(date(2026, 7, 1), 1)]
