"""Tests for the Thread RAG step: the retrieve and add_file actions on a real per-chat search"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.workflow.agents.rag import ThreadScopedRAG
from app.modules.workflow.engine.nodes.thread_rag_node import ThreadRAGNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from tests.unit.workflow.thread_rag_fakes import ACME_CHAT, GLOBEX_CHAT, make_search_fail

NODE_ID = "thread-rag-1"
ACME_FILE_TEXT = "Acme premium plan costs 40 euros per month."
RAG_VECTOR_CONFIG = {"chunk_size": 500, "chunk_overlap": 0}


@pytest.fixture
def thread_rag(thread_rag_backends):
    rag = ThreadScopedRAG()
    with patch("app.dependencies.injector.injector", MagicMock(get=lambda cls: rag)):
        yield rag


async def _run_step(chat_id: str, **node_data):
    node_config = {"id": NODE_ID, "type": "threadRAGNode", "data": {"name": "Chat search", **node_data}}
    state = WorkflowState(workflow={"nodes": [node_config], "config": {}}, thread_id=chat_id)
    output = await ThreadRAGNode(NODE_ID, node_config, state).execute()
    return output, state.node_execution_status[NODE_ID]


async def _add_acme_file():
    return await _run_step(
        ACME_CHAT,
        action="add_file",
        file_content=ACME_FILE_TEXT,
        file_name="acme-pricing.txt",
        file_id="file-1",
        ragVectorConfig=RAG_VECTOR_CONFIG,
    )


@pytest.mark.asyncio
async def test_add_file_action_succeeds_and_stores_the_file(thread_rag, thread_rag_backends):
    _embedder, store = thread_rag_backends

    output, status = await _add_acme_file()

    assert status["status"] == "success"
    assert output == {
        "success": True,
        "action": "add_file",
        "chat_id": ACME_CHAT,
        "file_name": "acme-pricing.txt",
        "file_id": "file-1",
    }
    assert any(ACME_FILE_TEXT in content for content in store.contents_of_chat(ACME_CHAT))


@pytest.mark.asyncio
async def test_retrieve_action_finds_the_file_added_to_the_same_chat(thread_rag):
    await _add_acme_file()

    output, status = await _run_step(
        ACME_CHAT, action="retrieve", query="premium plan cost", top_k=3, ragVectorConfig=RAG_VECTOR_CONFIG
    )

    assert status["status"] == "success"
    assert output["success"] is True
    assert output["count"] == 1
    assert ACME_FILE_TEXT in output["results"][0]["content"]
    assert output["results"][0]["metadata"]["filename"] == "acme-pricing.txt"


@pytest.mark.asyncio
async def test_retrieve_action_finds_a_message_added_by_the_add_action(thread_rag):
    await _run_step(ACME_CHAT, action="add", message="The Acme invoice number is 48213.", message_id="acme-1")

    output, _status = await _run_step(ACME_CHAT, action="retrieve", query="what is the invoice number")

    assert [result["content"] for result in output["results"]] == ["The Acme invoice number is 48213."]


@pytest.mark.asyncio
async def test_retrieve_action_in_another_chat_finds_nothing(thread_rag):
    await _add_acme_file()

    output, status = await _run_step(GLOBEX_CHAT, action="retrieve", query="premium plan cost")

    assert status["status"] == "success"
    assert output["results"] == []
    assert output["count"] == 0


@pytest.mark.asyncio
async def test_retrieve_action_fails_when_the_search_raises(thread_rag):
    await _add_acme_file()
    await make_search_fail(thread_rag, ACME_CHAT, RuntimeError("search outage"))

    _output, status = await _run_step(ACME_CHAT, action="retrieve", query="premium plan cost")

    assert status["status"] == "failed"
    assert status["error"].endswith("Search failed for chat chat-acme")
    assert "search outage" not in status["error"]


@pytest.mark.parametrize("top_k", [None, "5", 0])
@pytest.mark.asyncio
async def test_retrieve_action_works_with_a_missing_or_text_top_k(thread_rag, top_k):
    await _add_acme_file()

    output, status = await _run_step(ACME_CHAT, action="retrieve", query="premium plan cost", top_k=top_k)

    assert status["status"] == "success"
    assert output["count"] == 1


@pytest.mark.asyncio
async def test_retrieve_action_fails_when_the_search_service_cannot_start(thread_rag, thread_rag_backends):
    embedder, _store = thread_rag_backends
    embedder.fail_initialize = True

    _output, status = await _run_step(ACME_CHAT, action="retrieve", query="premium plan cost")

    assert status["status"] == "failed"
    assert "Search service is not available for chat chat-acme" in status["error"]
