"""Tests for the required-parameter guard in BaseTool.invoke().

A tool call whose required parameters are missing or empty must be refused
before the node runs, with an error observation that names the fields.
Optional parameters and non-empty values (including 0 and False) pass through.
"""

import pytest

from app.modules.workflow.agents.base_tool import BaseTool, is_empty_parameter_value

TICKET_PARAMETERS = {
    "email": {"type": "string", "required": True},
    "phone_number": {"type": "string", "required": True},
    "notes": {"type": "string", "required": False},
}


class _RecordingState:
    """Captures tool events the way WorkflowState.add_tool_event would."""

    def __init__(self):
        self.events = []

    def add_tool_event(self, **event):
        self.events.append(event)


class _CallSpy:
    """Stands in for a node's execute(); remembers whether it ran."""

    def __init__(self):
        self.calls = []

    async def __call__(self, payload):
        self.calls.append(payload)
        return {"status": 200, "data": {"id": 42}}


def _make_tool(parameters=TICKET_PARAMETERS, state=None, return_direct=False):
    spy = _CallSpy()
    tool = BaseTool(
        node_id="ticket",
        name="Ticket creation",
        description="Creates a ticket",
        parameters=parameters,
        function=spy,
        return_direct=return_direct,
        state=state,
    )
    return tool, spy


# --------------------------------------------------------------------------- #
# is_empty_parameter_value
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("value", [None, "", "   ", "null", "NULL", "None", " none "])
def test_empty_values_are_detected(value):
    assert is_empty_parameter_value(value) is True


@pytest.mark.parametrize("value", ["Guest", "Guest mode", "a@b.com", 0, 0.0, False, [], {}])
def test_real_values_are_not_empty(value):
    assert is_empty_parameter_value(value) is False


# --------------------------------------------------------------------------- #
# BaseTool.invoke() guard
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_empty_required_string_is_refused_and_function_not_called():
    tool, spy = _make_tool()

    out = await tool.invoke(email="", phone_number="123", notes="")

    assert spy.calls == []
    assert isinstance(out, str)
    assert out.startswith("ERROR:")
    assert "ticket_creation" in out
    assert "email" in out
    assert "phone_number" not in out


@pytest.mark.asyncio
async def test_all_missing_required_fields_are_listed():
    tool, spy = _make_tool()

    out = await tool.invoke(email="   ", phone_number="null")

    assert spy.calls == []
    assert "email, phone_number" in out


@pytest.mark.asyncio
async def test_omitted_required_parameter_is_refused():
    tool, spy = _make_tool()

    out = await tool.invoke(email="a@b.com")

    assert spy.calls == []
    assert "phone_number" in out


@pytest.mark.asyncio
async def test_placeholder_strings_are_refused():
    tool, spy = _make_tool()

    out = await tool.invoke(email="None", phone_number="NULL")

    assert spy.calls == []
    assert "email, phone_number" in out


@pytest.mark.asyncio
async def test_guest_phone_is_accepted():
    tool, spy = _make_tool()

    out = await tool.invoke(email="a@b.com", phone_number="Guest")

    assert len(spy.calls) == 1
    assert spy.calls[0] == {"parameters": {"email": "a@b.com", "phone_number": "Guest"}}
    assert out == {"status": 200, "data": {"id": 42}}


@pytest.mark.asyncio
async def test_empty_optional_parameter_is_accepted():
    tool, spy = _make_tool()

    await tool.invoke(email="a@b.com", phone_number="123", notes="")

    assert len(spy.calls) == 1


@pytest.mark.asyncio
async def test_required_zero_and_false_are_accepted():
    parameters = {
        "amount": {"type": "number", "required": True},
        "confirmed": {"type": "boolean", "required": True},
    }
    tool, spy = _make_tool(parameters=parameters)

    await tool.invoke(amount=0, confirmed=False)

    assert len(spy.calls) == 1


@pytest.mark.asyncio
async def test_tool_without_parameter_metadata_is_not_guarded():
    tool, spy = _make_tool(parameters={})

    await tool.invoke(anything="")

    assert len(spy.calls) == 1


@pytest.mark.asyncio
async def test_return_direct_tool_is_not_guarded():
    parameters = {"result": {"type": "string", "required": True}}
    tool, spy = _make_tool(parameters=parameters, return_direct=True)

    out = await tool.invoke(result="")

    assert len(spy.calls) == 1
    assert out == {"status": 200, "data": {"id": 42}}


@pytest.mark.asyncio
async def test_refused_call_is_recorded_as_failed():
    state = _RecordingState()
    tool, _ = _make_tool(state=state)

    await tool.invoke(email="", phone_number="123")

    assert len(state.events) == 1
    event = state.events[0]
    assert event["status"] == "failed"
    assert event["tool_name"] == "ticket_creation"
    assert event["arguments"] == {"email": "", "phone_number": "123"}
    assert event["result"] is None
    assert "email" in event["error"]
