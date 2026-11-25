"""A ticket tool tells the agent when its ticket was not created.

Runs the real agent tool, Tool Builder, workflow engine and Zendesk ticket node.
Stand-ins only at the edges: the saved Zendesk settings and the call to Zendesk.
"""

from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.modules.integration.zendesk import ZendeskAPIError, ZendeskConnector
from app.modules.workflow.agents.base_tool import FAILURE_SHOWN_TO_USER
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState

ZENDESK_NODE_MODULE = "app.modules.workflow.engine.nodes.zendesk_tool_node"
SETTINGS_ID = "11111111-1111-1111-1111-111111111111"
CREATED_TICKET = {"ticket": {"id": 7}}
PREPARED_TEXT = "Ticket prepared"
SENT_TEXT = "Ticket sent"
VALID_EMAIL = "jane@example.com"
DEFAULT_NAME = "Guest"
FILLER_EMAILS = ["unknown", "email_here", "no email", "n/a", "jane@example", "jane example.com", "07000000000"]


def _node(node_id: str, node_type: str, **data) -> dict:
    return {"id": node_id, "type": node_type, "data": data}


def _edge(source: str, target: str, source_handle: str = "output", target_handle: str = "input") -> dict:
    return {"source": source, "target": target, "sourceHandle": source_handle, "targetHandle": target_handle}


WORKFLOW = {
    "id": "wf-acme",
    "nodes": [
        _node("agent", "agentNode", name="Acme assistant"),
        _node(
            "tool",
            "toolBuilderNode",
            name="Create ticket",
            description="Opens a support ticket",
            inputSchema={
                "email": {"type": "string", "required": False},
                "name": {"type": "string", "required": False, "defaultValue": DEFAULT_NAME},
                "subject": {"type": "string", "required": True},
                "description": {"type": "string", "required": True},
            },
            forwardTemplate=(
                '{"source.email":"{{direct_input.parameters.email}}",'
                '"source.name":"{{direct_input.parameters.name}}",'
                '"source.subject":"{{direct_input.parameters.subject}}",'
                '"source.description":"{{direct_input.parameters.description}}"}'
            ),
        ),
        _node("prepare", "templateNode", name="Prepare ticket", template=PREPARED_TEXT),
        _node(
            "ticket",
            "zendeskTicketNode",
            name="Send ticket",
            subject="{{node_outputs.tool.subject}}",
            description="{{node_outputs.tool.description}}",
            requester_name="{{node_outputs.tool.name}}",
            requester_email="{{node_outputs.tool.email}}",
            app_settings_id=SETTINGS_ID,
        ),
        _node("sent", "templateNode", name="Mark ticket sent", template=SENT_TEXT),
    ],
    "edges": [
        _edge("tool", "agent", "output_tool", "input_tools"),
        _edge("tool", "prepare", "starter_processor"),
        _edge("prepare", "ticket"),
        _edge("ticket", "sent"),
    ],
}


class _SavedZendeskSettings:
    """Stands in for the saved Zendesk connection."""

    async def get_by_id(self, settings_id):
        values = {"zendesk_subdomain": "acme", "zendesk_email": "agent@example.com", "zendesk_api_token": "token"}
        return SimpleNamespace(values=values)


@contextmanager
def _zendesk(zendesk_request: AsyncMock):
    """Stands in for the saved settings and for the HTTP call to Zendesk."""
    services = SimpleNamespace(get=lambda service_type: _SavedZendeskSettings())
    with (
        patch(f"{ZENDESK_NODE_MODULE}.injector", services),
        patch(f"{ZENDESK_NODE_MODULE}.persist_requester_pii", AsyncMock()),
        patch.object(ZendeskConnector, "_make_request", zendesk_request),
    ):
        yield zendesk_request


def _with_unquoted_reference() -> dict:
    """The workflow with an optional text parameter that its forward template uses without quotes."""
    workflow = deepcopy(WORKFLOW)
    tool = next(node["data"] for node in workflow["nodes"] if node["id"] == "tool")
    tool["inputSchema"]["reference"] = {"type": "string", "required": False}
    tool["forwardTemplate"] = tool["forwardTemplate"][:-1] + ',"source.reference":{{direct_input.parameters.reference}}}'
    return workflow


def _ticket_tool(workflow: dict = WORKFLOW):
    """The agent's ticket tool and the run state of one customer message."""
    engine = WorkflowEngine(workflow)
    state = WorkflowState(workflow=engine.get_workflow(), thread_id="acme-thread-1", initial_values={"message": "Hi"})
    tools = engine.executable_node("agent", state).get_connected_nodes("tools")
    return tools[0], state


async def _call_ticket_tool(
    zendesk_request: AsyncMock, return_direct: bool = False, workflow: dict = WORKFLOW, **arguments
):
    tool, state = _ticket_tool(workflow)
    tool.return_direct = return_direct
    with _zendesk(zendesk_request):
        answer = await tool.invoke(subject="Refund request", description="Charged twice", **arguments)
    return answer, state


async def _open_ticket(zendesk_request: AsyncMock, email: str = VALID_EMAIL):
    return await _call_ticket_tool(zendesk_request, email=email)


def _zendesk_refusal(field: str) -> ZendeskAPIError:
    return ZendeskAPIError("Zendesk API", 422, "RecordInvalid", field)


def _sent_ticket(zendesk_request: AsyncMock) -> dict:
    return zendesk_request.await_args.kwargs["json"]["ticket"]


def _sent_requester(zendesk_request: AsyncMock) -> dict:
    return _sent_ticket(zendesk_request).get("requester", {})


def _step_status(state: WorkflowState, node_id: str) -> str:
    return (state.node_execution_status.get(node_id) or {}).get("status", "not run")


@pytest.mark.asyncio
async def test_created_ticket_returns_the_last_step_output():
    answer, state = await _open_ticket(AsyncMock(return_value=CREATED_TICKET))

    assert answer == SENT_TEXT
    assert _step_status(state, "sent") == "success"
    assert state.tool_events[-1]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_refused_ticket_is_reported_to_the_agent_as_a_failure():
    answer, state = await _open_ticket(AsyncMock(side_effect=_zendesk_refusal("tags")))

    assert "did not complete successfully" in answer
    assert "Zendesk ticket was not created" in answer
    assert "field=tags" in answer
    assert PREPARED_TEXT not in str(answer)
    assert _step_status(state, "sent") == "not run"
    assert state.tool_events[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_unreachable_zendesk_is_reported_to_the_agent_as_a_failure():
    network_error = HTTPException(status_code=500, detail="Zendesk API network error: ConnectTimeout")

    answer, state = await _open_ticket(AsyncMock(side_effect=network_error))

    assert "did not complete successfully" in answer
    assert "Zendesk could not be reached" in answer
    assert _step_status(state, "sent") == "not run"


@pytest.mark.asyncio
@pytest.mark.parametrize("email", FILLER_EMAILS)
async def test_ticket_with_an_unusable_email_is_not_sent(email):
    zendesk_request = AsyncMock(return_value=CREATED_TICKET)

    answer, state = await _open_ticket(zendesk_request, email=email)

    zendesk_request.assert_not_awaited()
    assert "was not run and no action was taken" in answer
    assert "not a valid email address" in answer
    assert "do not tell the user that anything failed" in answer
    assert "report that it could not be completed" not in answer
    assert email not in answer
    assert _step_status(state, "sent") == "not run"


@pytest.mark.asyncio
async def test_the_word_null_typed_as_the_email_is_not_sent():
    zendesk_request = AsyncMock(return_value=CREATED_TICKET)

    answer, _ = await _open_ticket(zendesk_request, email="null")

    zendesk_request.assert_not_awaited()
    assert "not a valid email address" in answer


@pytest.mark.asyncio
async def test_ticket_without_an_email_is_still_sent():
    zendesk_request = AsyncMock(return_value=CREATED_TICKET)

    answer, _ = await _open_ticket(zendesk_request, email="")

    assert answer == SENT_TEXT
    assert "email" not in _sent_requester(zendesk_request)


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [{}, {"email": None}], ids=["left out", "null"])
async def test_ticket_is_sent_when_the_agent_leaves_the_email_out(arguments):
    zendesk_request = AsyncMock(return_value=CREATED_TICKET)

    answer, _ = await _call_ticket_tool(zendesk_request, **arguments)

    assert answer == SENT_TEXT
    assert "email" not in _sent_requester(zendesk_request)


@pytest.mark.asyncio
async def test_left_out_value_with_a_default_reaches_the_ticket_as_the_default():
    zendesk_request = AsyncMock(return_value=CREATED_TICKET)

    await _open_ticket(zendesk_request)

    assert _sent_requester(zendesk_request)["name"] == DEFAULT_NAME


@pytest.mark.asyncio
async def test_left_out_value_used_without_quotes_keeps_the_tool_working():
    zendesk_request = AsyncMock(return_value=CREATED_TICKET)

    answer, _ = await _call_ticket_tool(zendesk_request, workflow=_with_unquoted_reference(), email=VALID_EMAIL)

    assert answer == SENT_TEXT
    zendesk_request.assert_awaited_once()


@pytest.mark.asyncio
async def test_valid_email_reaches_zendesk_without_surrounding_spaces():
    zendesk_request = AsyncMock(return_value=CREATED_TICKET)

    await _open_ticket(zendesk_request, email=f"  {VALID_EMAIL} ")

    assert _sent_requester(zendesk_request)["email"] == VALID_EMAIL


@pytest.mark.asyncio
async def test_requester_refused_by_zendesk_asks_for_another_email():
    answer, state = await _open_ticket(AsyncMock(side_effect=_zendesk_refusal("requester")))

    assert "was not run and no action was taken" in answer
    assert "Ask the user for a different email address" in answer
    assert "report that it could not be completed" not in answer
    assert _step_status(state, "sent") == "not run"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "zendesk_request, email",
    [
        (AsyncMock(return_value=CREATED_TICKET), "unknown"),
        (AsyncMock(side_effect=_zendesk_refusal("tags")), VALID_EMAIL),
    ],
    ids=["unusable email", "ticket refused"],
)
async def test_failed_tool_that_replies_to_the_user_directly_gives_no_agent_instructions(zendesk_request, email):
    answer, state = await _call_ticket_tool(zendesk_request, return_direct=True, email=email)

    assert answer == FAILURE_SHOWN_TO_USER
    assert state.tool_events[-1]["status"] == "failed"
