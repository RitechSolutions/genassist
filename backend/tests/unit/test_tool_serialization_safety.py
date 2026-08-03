"""Regression tests for tool-object serialization safety.

These guard the fix for the ML-worker freeze where an agent that *called* a tool
produced a reference cycle (workflow state -> node input -> tool -> state) that
stalled ``sanitize_for_json`` and wedged the solo worker. The three layers of
defence are exercised here: the dangerous wire is removed (tools_reference
stripped), the back-reference is weak, and the sanitizer is cycle/depth/size safe.
"""

import gc
import time

from app.modules.workflow.agents.base_tool import BaseTool
from app.modules.workflow.engine.nodes.ml.ml_utils import (
    _MAX_SANITIZE_DEPTH,
    sanitize_for_json,
)
from app.modules.workflow.engine.workflow_state import _strip_live_tool_refs


class _FakeState:
    """Minimal WorkflowState stand-in exposing an add_tool_event sink."""

    def __init__(self):
        self.node_execution_status = {}
        self.events = []

    def add_tool_event(self, **kwargs):
        self.events.append(kwargs)


def _make_tool(state):
    return BaseTool(
        node_id="tool-1",
        name="search handbook",
        description="d",
        parameters={},
        function=lambda payload: "ok",
        state=state,
    )


# --- Step 2: BaseTool holds the workflow state weakly ---

def test_base_tool_state_resolves_but_is_not_a_strong_field():
    state = _FakeState()
    tool = _make_tool(state)
    assert tool.state is state
    assert "state" not in vars(tool)  # no strong ref that sanitize would follow
    assert "_state_ref" in vars(tool)


def test_base_tool_state_is_none_after_collection():
    state = _FakeState()
    tool = _make_tool(state)
    del state
    gc.collect()
    assert tool.state is None


def test_base_tool_accepts_none_state():
    assert _make_tool(None).state is None


def test_called_tool_still_records_event():
    state = _FakeState()
    tool = _make_tool(state)
    tool._record_event({"q": "hi"}, "answer", status="succeeded")
    assert len(state.events) == 1
    assert state.events[0]["tool_id"] == "tool-1"


# --- Step 3: sanitize_for_json is cycle / depth / size safe ---

def test_sanitize_breaks_direct_dict_cycle():
    node = {}
    node["self"] = node
    assert sanitize_for_json(node)["self"] == "<cycle>"


def test_sanitize_survives_state_tool_cycle_fast():
    # The exact production shape: state -> node_execution_status -> tool -> state.
    state = _FakeState()
    tool = _make_tool(state)
    state.node_execution_status = {"agent": {"input": {"tools_reference": [tool]}}}
    start = time.monotonic()
    out = sanitize_for_json({"nodeExecutionStatus": state.node_execution_status})
    assert time.monotonic() - start < 5.0
    assert isinstance(out, dict)


def test_sanitize_is_depth_bounded():
    root = current = {}
    for _ in range(_MAX_SANITIZE_DEPTH + 50):
        current["x"] = {}
        current = current["x"]
    assert sanitize_for_json(root) is not None  # no RecursionError, returns


def test_sanitize_preserves_shared_acyclic_refs():
    shared = {"a": 1}
    out = sanitize_for_json({"one": shared, "two": shared})
    assert out == {"one": {"a": 1}, "two": {"a": 1}}  # diamond kept, not "<cycle>"


# --- Step 1: tools_reference stripped from serialized traces ---

def test_strip_removes_tools_reference_when_tool_called():
    state = _FakeState()
    tool = _make_tool(state)
    node_status = {"agent": {"input": {"prompt": "hi", "tools_reference": [tool]}, "status": "success"}}
    cleaned = _strip_live_tool_refs(node_status)
    assert "tools_reference" not in cleaned["agent"]["input"]
    assert cleaned["agent"]["input"]["prompt"] == "hi"
    assert "tools_reference" in node_status["agent"]["input"]  # original untouched


def test_strip_is_noop_when_no_tool_called():
    node_status = {"agent": {"input": {"prompt": "hi"}, "status": "success"}}
    assert _strip_live_tool_refs(node_status) == node_status


def test_bound_event_value_truncates_long_strings():
    from app.modules.workflow.engine.workflow_state import (
        _MAX_EVENT_VALUE_CHARS,
        _bound_event_value,
    )

    long_result = "x" * (_MAX_EVENT_VALUE_CHARS + 100)
    out = _bound_event_value(long_result)
    assert isinstance(out, dict) and out["_truncated"] is True
    assert out["chars"] == len(long_result)
    assert len(out["preview"]) == _MAX_EVENT_VALUE_CHARS


def test_bound_event_value_keeps_short_strings():
    from app.modules.workflow.engine.workflow_state import _bound_event_value

    assert _bound_event_value("short result") == "short result"
