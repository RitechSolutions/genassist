"""Engine-level usage capture seam"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import app.modules.workflow.engine.workflow_engine as engine_module
from app.core.utils import background_tasks
from app.modules.workflow.engine.workflow_engine import WorkflowEngine

_WORKFLOW = {
    "config": {"id": "wf1"},
    "id": "wf1",
    "nodes": [{"id": "n1", "type": "agentNode", "data": {}}],
    "edges": [],
}


def _engine():
    return WorkflowEngine(dict(_WORKFLOW))


def _run(engine, **kwargs):
    return engine.execute_from_node(
        start_node_id="n1",
        input_data={"message": "hi"},
        thread_id="11111111-1111-1111-1111-111111111111",
        persist=False,
        **kwargs,
    )


def _recording(usage=None):

    async def _execute(self, node_id, state, visited, **kwargs):
        for entry in usage or [{"input_tokens": 1, "output_tokens": 1}]:
            state.add_llm_usage(**entry)

    return patch.object(WorkflowEngine, "_execute_from_node_recursive", _execute)


def _failing(error, usage=None):
    async def _execute(self, node_id, state, visited, **kwargs):
        for entry in usage or [{"input_tokens": 1, "output_tokens": 1}]:
            state.add_llm_usage(**entry)
        raise error

    return patch.object(WorkflowEngine, "_execute_from_node_recursive", _execute)


class TestExecutionOutcome:
    @pytest.mark.asyncio
    async def test_successful_run_is_recorded_as_returned(self):
        engine = _engine()
        recorder = AsyncMock()
        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder):
            await _run(engine, usage_context=SimpleNamespace(source="chat"))

        assert recorder.await_args.kwargs["execution_outcome"] == "returned"

    @pytest.mark.asyncio
    async def test_raising_run_is_recorded_as_raised(self):
        engine = _engine()
        recorder = AsyncMock()
        with _failing(RuntimeError("node exploded")), patch.object(
            WorkflowEngine, "_record_llm_usage_safe", recorder
        ):
            with pytest.raises(RuntimeError):
                await _run(engine, usage_context=SimpleNamespace(source="chat"))

        assert recorder.await_args.kwargs["execution_outcome"] == "raised"
        assert recorder.await_args.args[0].llm_usage

    @pytest.mark.asyncio
    async def test_cancelled_run_still_counts_as_raised(self):
        engine = _engine()
        recorder = AsyncMock()
        with _failing(asyncio.CancelledError()), patch.object(
            WorkflowEngine, "_record_llm_usage_safe", recorder
        ):
            with pytest.raises(asyncio.CancelledError):
                await _run(engine, usage_context=SimpleNamespace(source="chat"))

        assert recorder.await_args.kwargs["execution_outcome"] == "raised"


class TestUsageHandover:
    @pytest.mark.asyncio
    async def test_nested_run_appends_into_the_parent_sink(self):
        engine = _engine()
        sink = []
        recorder = AsyncMock()
        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder):
            await _run(engine, usage_sink=sink)

        assert len(sink) == 1
        recorder.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sink_receives_usage_even_when_the_child_raises(self):
        engine = _engine()
        sink = []
        with _failing(RuntimeError("child exploded")):
            with pytest.raises(RuntimeError):
                await _run(engine, usage_sink=sink)

        assert len(sink) == 1

    @pytest.mark.asyncio
    async def test_sink_wins_over_context_when_both_are_passed(self, caplog):
        engine = _engine()
        sink = []
        recorder = AsyncMock()
        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder):
            await _run(engine, usage_sink=sink, usage_context=SimpleNamespace(source="chat"))

        assert len(sink) == 1
        recorder.assert_not_awaited()
        assert "sink wins" in caplog.text

    @pytest.mark.asyncio
    async def test_run_without_threading_records_nothing(self):
        engine = _engine()
        recorder = AsyncMock()
        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder):
            await _run(engine)

        recorder.assert_not_awaited()


def _deferred(**kwargs):
    return SimpleNamespace(source="chat", defer_capture=True, **kwargs)


class TestDeferredCapture:
    @pytest.fixture(autouse=True)
    def _empty_registry(self):
        background_tasks._TASKS.clear()
        yield
        background_tasks._TASKS.clear()

    @pytest.mark.asyncio
    async def test_capture_is_scheduled_instead_of_awaited(self):
        engine = _engine()
        recorder = AsyncMock()
        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder):
            await _run(engine, usage_context=_deferred())
            recorder.assert_not_awaited()
            assert len(background_tasks._TASKS) == 1

            await background_tasks.drain(timeout=5.0)
            await asyncio.sleep(0)

        recorder.assert_awaited_once()
        assert recorder.await_args.kwargs["execution_outcome"] == "returned"
        assert not background_tasks._TASKS

    @pytest.mark.asyncio
    async def test_snapshot_survives_the_state_being_reset(self):
        engine = _engine()
        recorder = AsyncMock()
        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder):
            state = await _run(engine, usage_context=_deferred())
            state.llm_usage.clear()
            await background_tasks.drain(timeout=5.0)

        assert len(recorder.await_args.args[0].llm_usage) == 1

    @pytest.mark.asyncio
    async def test_occurred_at_is_stamped_at_scheduling_time(self):
        engine = _engine()
        recorder = AsyncMock()
        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder), patch.object(
            engine_module, "utc_now", return_value="scheduled-at"
        ):
            await _run(engine, usage_context=_deferred())
            await background_tasks.drain(timeout=5.0)

        assert recorder.await_args.kwargs["occurred_at"] == "scheduled-at"

    @pytest.mark.asyncio
    async def test_falls_back_to_recording_inline_when_scheduling_fails(self, caplog):
        engine = _engine()
        recorder = AsyncMock()

        def _no_spawn(coro, *, name):
            coro.close()
            raise RuntimeError("cannot schedule")

        with _recording(), patch.object(WorkflowEngine, "_record_llm_usage_safe", recorder), patch.object(
            engine_module, "spawn", _no_spawn
        ):
            await _run(engine, usage_context=_deferred())

        recorder.assert_awaited_once()
        assert recorder.await_args.kwargs.get("occurred_at") is None
        assert "recording inline" in caplog.text
