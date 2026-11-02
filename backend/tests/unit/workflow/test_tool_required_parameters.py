"""Tests for the required-parameter guard in BaseTool.invoke().

A tool call whose required parameters are missing or empty must be refused
before the node runs, with an error observation that names the fields.
Optional parameters and non-empty values (including 0 and False) pass through.
"""

import pytest

from app.modules.workflow.agents.agent_utils import convert_parameter_type, validate_tool_parameters
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

@pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
def test_empty_values_are_detected(value):
    assert is_empty_parameter_value(value) is True


@pytest.mark.parametrize(
    "value", ["Guest", "Guest mode", "a@b.com", "none", "None", "null", "NULL", 0, 0.0, False, [], {}]
)
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

    out = await tool.invoke(email="   ", phone_number=None)

    assert spy.calls == []
    assert "email, phone_number" in out


@pytest.mark.asyncio
async def test_omitted_required_parameter_is_refused():
    tool, spy = _make_tool()

    out = await tool.invoke(email="a@b.com")

    assert spy.calls == []
    assert "phone_number" in out


@pytest.mark.asyncio
async def test_none_and_null_text_answers_are_accepted():
    parameters = {"allergies": {"type": "string", "required": True}}
    tool, spy = _make_tool(parameters=parameters)

    await tool.invoke(allergies="none")
    await tool.invoke(allergies="null")

    assert spy.calls == [
        {"parameters": {"allergies": "none"}},
        {"parameters": {"allergies": "null"}},
    ]


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


# --------------------------------------------------------------------------- #
# JSON null through parameter validation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("param_type", ["string", "number", "integer", "boolean"])
def test_json_null_is_kept_as_null(param_type):
    errors = []

    assert convert_parameter_type(None, param_type, "field", errors) is None
    assert errors == []


@pytest.mark.asyncio
async def test_json_null_required_parameter_is_refused_with_ask_the_user():
    tool, spy = _make_tool()

    validated = validate_tool_parameters(tool, {"email": None, "phone_number": "123"})
    out = await tool.invoke(**validated)

    assert "email" not in validated
    assert spy.calls == []
    assert "ask the user" in out


def test_json_null_required_parameter_of_return_direct_tool_is_reported_missing():
    parameters = {"order_id": {"type": "integer", "required": True}}
    tool, _ = _make_tool(parameters=parameters, return_direct=True)

    with pytest.raises(ValueError, match="Required parameter 'order_id' is missing"):
        validate_tool_parameters(tool, {"order_id": None})


def test_omitted_required_parameter_is_still_reported_missing():
    tool, _ = _make_tool()

    with pytest.raises(ValueError, match="Required parameter 'email' is missing"):
        validate_tool_parameters(tool, {"phone_number": "123"})


def test_json_null_optional_parameter_gets_its_default():
    parameters = {"priority": {"type": "string", "default": "normal"}}
    tool, _ = _make_tool(parameters=parameters)

    assert validate_tool_parameters(tool, {"priority": None}) == {"priority": "normal"}


def test_json_null_optional_parameter_without_default_is_left_out():
    tool, _ = _make_tool()

    validated = validate_tool_parameters(tool, {"email": "a@b.com", "phone_number": "123", "notes": None})

    assert validated == {"email": "a@b.com", "phone_number": "123"}
