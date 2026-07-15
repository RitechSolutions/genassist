"""
Unit tests for OpenAI file upload functionality.
"""
import pytest
import tempfile
import os
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from app.services.open_ai_fine_tuning import OpenAIFineTuningService
from app.repositories.openai_fine_tuning import FineTuningRepository
from app.services.fine_tuning_event import FineTuningEventService
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException


@pytest.fixture
def mock_repository():
    """Create a mocked repository."""
    return AsyncMock(spec=FineTuningRepository)


@pytest.fixture
def mock_event_service():
    """Create a mocked event service."""
    return AsyncMock(spec=FineTuningEventService)


@pytest.fixture
def mock_openai_client():
    """Create a mocked OpenAI client."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_response.id = "file-abc123"
    mock_response.filename = "test.pdf"
    mock_response.purpose = "user_data"
    mock_response.bytes = 1024
    client.files.create = AsyncMock(return_value=mock_response)
    return client


@pytest.fixture
def openai_service(mock_repository, mock_event_service, mock_openai_client):
    """Create OpenAIFineTuningService with mocked dependencies."""
    service = OpenAIFineTuningService(
        repository=mock_repository,
        event_service=mock_event_service,
        agent_config_service=MagicMock(),
        agent_log_repo=MagicMock(),
        conversation_repo=MagicMock(),
        app_settings_service=AsyncMock(),
    )
    service.client = mock_openai_client
    return service


@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for testing."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pdf') as f:
        f.write(b"Test PDF content")
        path = f.name
    yield path
    os.unlink(path)


@pytest.mark.asyncio
async def test_upload_file_for_chat_success(openai_service, mock_repository, mock_openai_client, temp_pdf_file):
    """Test successful file upload to OpenAI for chat."""
    file_id = await openai_service.upload_file_for_chat(
        file_url=temp_pdf_file,
        filename="test.pdf",
        purpose="user_data"
    )

    assert file_id == "file-abc123"
    mock_openai_client.files.create.assert_called_once()
    call_kwargs = mock_openai_client.files.create.call_args.kwargs
    assert call_kwargs["purpose"] == "user_data"
    assert call_kwargs["file"][0] == "test.pdf"
    mock_repository.create_file_record.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_for_chat_db_error_continues(openai_service, mock_repository, mock_openai_client, temp_pdf_file):
    """Test that DB errors don't fail the upload."""
    mock_repository.create_file_record.side_effect = Exception("DB error")

    file_id = await openai_service.upload_file_for_chat(
        file_url=temp_pdf_file,
        filename="test.pdf",
        purpose="user_data"
    )

    assert file_id == "file-abc123"
    mock_openai_client.files.create.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_for_chat_openai_error_raises(openai_service, mock_openai_client, temp_pdf_file):
    """Test that OpenAI errors are properly raised."""
    mock_openai_client.files.create.side_effect = Exception("OpenAI API error")

    with pytest.raises(AppException) as exc_info:
        await openai_service.upload_file_for_chat(
            file_url=temp_pdf_file,
            filename="test.pdf",
            purpose="user_data"
        )

    assert exc_info.value.error_key == ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI


@pytest.mark.asyncio
async def test_upload_file_for_chat_file_not_found(openai_service):
    """Test that file not found raises error."""
    with pytest.raises(AppException) as exc_info:
        await openai_service.upload_file_for_chat(
            file_url="/nonexistent/file.pdf",
            filename="test.pdf",
            purpose="user_data"
        )

    assert exc_info.value.error_key == ErrorKey.ERROR_UPLOAD_FILE_OPEN_AI


# ---------------------------------------------------------------------------
# Training-example builders (_build_jsonl_entry, _build_memory_jsonl_entry)
# ---------------------------------------------------------------------------


def _msg(msg_id, seq, speaker, text):
    return SimpleNamespace(
        id=msg_id, sequence_number=seq, speaker=speaker, text=text
    )


def _log(transcript_message_id, *, output="", steps=None):
    """Build a stub agent log whose raw_response mirrors the real engine shape."""
    raw = {
        "row_agent_response": {
            "output": output,
            "state": {
                "nodeExecutionStatus": {
                    "agent-1": {
                        "type": "agentNode",
                        "output": {"message": output, "steps": steps or []},
                    }
                }
            },
        }
    }
    return SimpleNamespace(
        transcript_message_id=transcript_message_id,
        raw_response=json.dumps(raw),
    )


TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "get_order_status", "parameters": {}}}
]


def test_build_jsonl_entry_tool_call_with_result(openai_service):
    """ToolAgent-shaped step (has result) -> assistant tool_calls + tool + final."""
    messages = [
        _msg("u1", 1, "customer", "Where is my order?"),
        _msg("a1", 2, "agent", "It ships tomorrow."),
    ]
    log = _log(
        "a1",
        output="It ships tomorrow.",
        steps=[
            {
                "step": "1_tool_result",
                "tool": "get_order_status",
                "args": {"order_id": "123"},
                "result": "ships 2026-07-15",
            }
        ],
    )

    entry = openai_service._build_jsonl_entry(log, messages, "You are helpful.", TOOL_SCHEMAS)

    roles = [m["role"] for m in entry["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    tool_call_msg = entry["messages"][2]
    assert tool_call_msg["tool_calls"][0]["function"]["name"] == "get_order_status"
    tool_result_msg = entry["messages"][3]
    assert tool_result_msg["tool_call_id"] == tool_call_msg["tool_calls"][0]["id"]
    assert tool_result_msg["content"] == "ships 2026-07-15"
    assert entry["messages"][4]["content"] == "It ships tomorrow."
    assert entry["tools"] == TOOL_SCHEMAS


def test_build_jsonl_entry_react_no_result_falls_back(openai_service):
    """ReActAgentLC-shaped step (no result) -> plain assistant content, no tool turns."""
    messages = [
        _msg("u1", 1, "user", "Where is my order?"),
        _msg("a1", 2, "agent", "It ships tomorrow."),
    ]
    log = _log(
        "a1",
        output="It ships tomorrow.",
        steps=[
            {
                "iteration": 1,
                "thought": "look it up",
                "tool_name": "get_order_status",
                "tool_args": {"order_id": "123"},
            }
        ],
    )

    entry = openai_service._build_jsonl_entry(log, messages, "You are helpful.", TOOL_SCHEMAS)

    roles = [m["role"] for m in entry["messages"]]
    assert roles == ["system", "user", "assistant"]
    assert entry["messages"][2]["content"] == "It ships tomorrow."
    assert "tools" not in entry


def test_build_jsonl_entry_plain_no_steps(openai_service):
    """No steps -> plain system/user/assistant triple."""
    messages = [
        _msg("u1", 1, "customer", "Hi"),
        _msg("a1", 2, "agent", "Hello!"),
    ]
    log = _log("a1", output="Hello!")

    entry = openai_service._build_jsonl_entry(log, messages, "sys", [])

    assert [m["role"] for m in entry["messages"]] == ["system", "user", "assistant"]
    assert entry["messages"][2]["content"] == "Hello!"


def test_build_jsonl_entry_include_tools_false_strips_tools(openai_service):
    """include_tools=False -> plain final answer even when a tool result exists."""
    messages = [
        _msg("u1", 1, "customer", "Where is my order?"),
        _msg("a1", 2, "agent", "It ships tomorrow."),
    ]
    log = _log(
        "a1",
        output="It ships tomorrow.",
        steps=[
            {"tool": "get_order_status", "args": {"order_id": "123"}, "result": "ships 2026-07-15"}
        ],
    )

    entry = openai_service._build_jsonl_entry(
        log, messages, "sys", TOOL_SCHEMAS, include_tools=False
    )

    assert [m["role"] for m in entry["messages"]] == ["system", "user", "assistant"]
    assert entry["messages"][2]["content"] == "It ships tomorrow."
    assert "tools" not in entry


def test_build_memory_jsonl_entry_multi_turn(openai_service):
    """Memory mode -> one example with a single system msg and ordered turns."""
    messages = [
        _msg("u1", 1, "customer", "What's the return policy?"),
        _msg("a1", 2, "agent", "30 days."),
        _msg("u2", 3, "customer", "And for the item I bought last week?"),
        _msg("a2", 4, "agent", "Still within the 30 days."),
    ]
    logs = [_log("a1", output="30 days."), _log("a2", output="Still within the 30 days.")]

    entry = openai_service._build_memory_jsonl_entry(messages, logs, "You are helpful.", [])

    roles = [m["role"] for m in entry["messages"]]
    assert roles == ["system", "user", "assistant", "user", "assistant"]
    assert entry["messages"][0]["content"] == "You are helpful."
    assert entry["messages"][3]["content"] == "And for the item I bought last week?"
    assert entry["messages"][4]["content"] == "Still within the 30 days."
    assert "tools" not in entry


def test_build_memory_jsonl_entry_with_tool_call(openai_service):
    """Memory mode expands an agent turn with tool results and adds tools."""
    messages = [
        _msg("u1", 1, "customer", "Where is my order?"),
        _msg("a1", 2, "agent", "It ships tomorrow."),
    ]
    logs = [
        _log(
            "a1",
            output="It ships tomorrow.",
            steps=[
                {
                    "tool": "get_order_status",
                    "args": {"order_id": "123"},
                    "result": "ships 2026-07-15",
                }
            ],
        )
    ]

    entry = openai_service._build_memory_jsonl_entry(messages, logs, "sys", TOOL_SCHEMAS)

    roles = [m["role"] for m in entry["messages"]]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    assert entry["tools"] == TOOL_SCHEMAS


def test_build_memory_jsonl_entry_tool_call_ids_unique_across_turns(openai_service):
    """Multiple tool-using agent turns in one example must have unique tool_call_ids."""
    messages = [
        _msg("u1", 1, "customer", "Where is my order?"),
        _msg("a1", 2, "agent", "It ships tomorrow."),
        _msg("u2", 3, "customer", "And my other one?"),
        _msg("a2", 4, "agent", "That one shipped."),
    ]
    logs = [
        _log("a1", output="It ships tomorrow.",
             steps=[{"tool": "get_order_status", "args": {"id": "1"}, "result": "ships 2026-07-15"}]),
        _log("a2", output="That one shipped.",
             steps=[{"tool": "get_order_status", "args": {"id": "2"}, "result": "shipped"}]),
    ]

    entry = openai_service._build_memory_jsonl_entry(messages, logs, "sys", TOOL_SCHEMAS)

    call_ids = [
        tc["id"]
        for m in entry["messages"]
        if m["role"] == "assistant" and m.get("tool_calls")
        for tc in m["tool_calls"]
    ]
    tool_result_ids = [m["tool_call_id"] for m in entry["messages"] if m["role"] == "tool"]

    assert len(call_ids) == 2
    assert len(set(call_ids)) == 2, f"tool_call_ids collided: {call_ids}"
    # every tool-result message maps to exactly one preceding call id
    assert set(tool_result_ids) == set(call_ids)
