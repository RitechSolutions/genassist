"""Documents the visitor attaches reach the model as text, whichever node answers.

Before, only a File Reader node read chat documents; an Agent or LLM Model node never saw
them ("please provide the PDF"). Only files uploaded to the same conversation are read, so
a visitor cannot make the agent read another conversation's file by sending its id.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.api.v1.routes  # noqa: F401  (loads the routes first; the use case module imports them circularly)
from app.modules.workflow.agents import document_attachments as docs
from app.modules.workflow.agents.agent_runtime import run_agent_once
from app.use_cases import chat_as_client_use_case

CONVERSATION = uuid.uuid4()
NOTES = b"Project codename: ZEBRA-4471\nLaunch date: 14 March 2027\n"


def _resolved_txt(name="notes.txt"):
    return {"name": name, "type": "text/plain", "file_id": str(uuid.uuid4()), "file_storage_provider": "local"}


def _file_service(content=NOTES):
    service = MagicMock()
    service.download_file = AsyncMock(return_value=(SimpleNamespace(original_filename="notes.txt", name="x"), content))
    service.get_file_content_from_url = AsyncMock(return_value=content)
    return service


@pytest.fixture
def file_service():
    service = _file_service()
    injector = MagicMock()
    injector.get.return_value = service
    with patch("app.dependencies.injector.injector", injector):
        yield service


# ---------------------------------------------------------------- ownership


def test_only_this_conversations_uploads_count():
    own = SimpleNamespace(path=f"agents_config/upload-chat-files/{CONVERSATION}/a.pdf")
    s3 = SimpleNamespace(path=f"tenants/acme/agents_config/upload-chat-files/{CONVERSATION}/a.pdf")
    other = SimpleNamespace(path=f"agents_config/upload-chat-files/{uuid.uuid4()}/a.pdf")
    knowledge = SimpleNamespace(path="kb/handbook.pdf")
    assert chat_as_client_use_case.is_chat_upload_of(own, CONVERSATION)
    assert chat_as_client_use_case.is_chat_upload_of(s3, CONVERSATION)
    assert not chat_as_client_use_case.is_chat_upload_of(other, CONVERSATION)
    assert not chat_as_client_use_case.is_chat_upload_of(knowledge, CONVERSATION)


@pytest.mark.asyncio
async def test_a_file_from_another_conversation_is_not_resolved(monkeypatch):
    foreign = SimpleNamespace(
        id=uuid.uuid4(), name="secret.pdf", mime_type="application/pdf", storage_provider="local",
        storage_path="/data", path=f"agents_config/upload-chat-files/{uuid.uuid4()}/secret.pdf",
    )
    service = MagicMock()
    service.get_file_by_id = AsyncMock(return_value=foreign)
    service.get_file_url = AsyncMock()
    recorded = AsyncMock()
    monkeypatch.setattr(chat_as_client_use_case, "process_file_upload_from_chat", recorded)
    attachment = {"name": "secret.pdf", "type": "application/pdf", "file_id": str(foreign.id)}

    await chat_as_client_use_case.process_attachments_from_metadata(
        base_url="http://localhost:8000", conversation_id=CONVERSATION,
        model=SimpleNamespace(metadata={"attachments": [attachment]}),
        tenant_id="master", current_user_id=uuid.uuid4(), file_manager_service=service,
    )

    assert not docs.is_resolved(attachment)
    service.get_file_url.assert_not_awaited()
    recorded.assert_not_awaited()


# ---------------------------------------------------------------- building the text


def test_a_long_document_is_cut_with_a_note():
    section = docs.document_section("big.txt", "x" * (docs.DOC_CHAR_LIMIT + 500))
    assert section.startswith("=== big.txt ===\n")
    assert section.endswith("[... 500 more characters of big.txt not shown]")


def test_an_unreadable_document_says_so():
    assert docs.document_section("scan.pdf", "  ") == "=== scan.pdf ===\n[Could not extract text from scan.pdf]"


def test_too_many_documents_are_left_out_with_a_note():
    sections = ["a" * 20, "b" * 20, "c" * 20]
    assert docs.cap_sections(sections, total_limit=45) == ["a" * 20, "b" * 20, "[1 more attached document(s) not shown: too much text]"]


def test_the_message_gets_the_documents_or_a_stand_in():
    assert docs.with_documents("hi", None) == "hi"
    assert docs.with_documents("Summarise it", "BLOCK") == "Summarise it\n\nBLOCK"
    assert docs.with_documents("", "BLOCK") == f"{docs.DOCUMENT_ONLY_PROMPT}\n\nBLOCK"


def test_a_file_reader_node_on_chat_attachments_means_the_message_stays_as_is():
    reader = {"nodes": [{"type": "fileReaderNode", "data": {"fileSource": "chatAttachment"}}]}
    fixed = {"nodes": [{"type": "fileReaderNode", "data": {"fileSource": "upload"}}]}
    assert docs.workflow_reads_chat_documents(reader)
    assert not docs.workflow_reads_chat_documents(fixed)
    assert not docs.workflow_reads_chat_documents(None)


@pytest.mark.asyncio
async def test_the_block_holds_the_documents_text(file_service):
    block = await docs.documents_block([_resolved_txt(), {"name": "p.png", "type": "image/png", "file_id": "x", "file_storage_provider": "local"}])
    assert block.startswith(docs.DOCUMENTS_PREAMBLE)
    assert "=== notes.txt ===" in block and "ZEBRA-4471" in block
    assert "p.png" not in block


@pytest.mark.asyncio
async def test_documents_the_server_did_not_resolve_are_never_read(file_service):
    forged = {"name": "secret.pdf", "type": "application/pdf", "file_id": str(uuid.uuid4())}
    assert await docs.documents_block([forged]) is None
    file_service.download_file.assert_not_awaited()


# ---------------------------------------------------------------- the agent sees them


async def _run(state, user_prompt):
    agent = MagicMock()
    agent.invoke = AsyncMock(return_value={"response": "ok", "status": "success"})
    agent.cache_split_decision = (False, None)
    with patch("app.modules.workflow.agents.agent_runtime.ToolAgent", MagicMock(return_value=agent)), patch(
        "app.modules.workflow.engine.llm_usage_tracking.merge_llm_usage_from_result", AsyncMock()
    ):
        await run_agent_once(
            state=state, node_id="agent-1", provider_id="p", fallback_chain_id=None, agent_type="ToolSelector",
            system_prompt="sys", user_prompt=user_prompt, tools=[], max_iterations=3, llm_model="model",
        )
    return agent.invoke.await_args.args[0]


def _state(attachments, workflow=None):
    return SimpleNamespace(
        get_value=lambda key, default=None: attachments if key == "attachments" else default,
        workflow=workflow or {"nodes": []},
    )


@pytest.mark.asyncio
async def test_the_agent_gets_the_document_with_the_question(file_service):
    prompt = await _run(_state([_resolved_txt()]), "What is the codename?")
    assert prompt.startswith("What is the codename?\n\n" + docs.DOCUMENTS_PREAMBLE)
    assert "ZEBRA-4471" in prompt


@pytest.mark.asyncio
async def test_a_document_sent_alone_gets_the_stand_in(file_service):
    prompt = await _run(_state([_resolved_txt()]), "")
    assert prompt.startswith(docs.DOCUMENT_ONLY_PROMPT)


@pytest.mark.asyncio
async def test_no_documents_leaves_the_message_alone(file_service):
    assert await _run(_state([]), "Hello") == "Hello"
    file_service.download_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_workflow_with_a_file_reader_is_not_sent_the_text_twice(file_service):
    reader = {"nodes": [{"type": "fileReaderNode", "data": {"fileSource": "chatAttachment"}}]}
    assert await _run(_state([_resolved_txt()], reader), "What is the codename?") == "What is the codename?"


@pytest.mark.asyncio
async def test_the_documents_are_read_once_per_run(file_service):
    state = _state([_resolved_txt()])
    await _run(state, "first")
    await _run(state, "second (after a delegation)")
    assert file_service.download_file.await_count == 1


# ---------------------------------------------------------------- File Reader keeps its rules


@pytest.mark.asyncio
async def test_the_file_reader_still_reads_by_id_without_a_cap(file_service):
    from app.modules.workflow.engine.nodes.file_reader_node import FileReaderNode

    long_text = ("line of text " * 3000).encode()
    file_service.download_file = AsyncMock(return_value=(SimpleNamespace(original_filename="long.txt", name="x"), long_text))
    node = FileReaderNode.__new__(FileReaderNode)
    node.get_state = lambda: _state([{"name": "long.txt", "type": "text/plain", "file_id": str(uuid.uuid4())}])
    out = await node._read_chat_documents()
    assert out.startswith("=== long.txt ===")
    assert len(out) > docs.DOC_CHAR_LIMIT and "not shown" not in out
