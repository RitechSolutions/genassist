"""Tests for ThreadScopedRAG: the search within one chat, adding a file and purging a chat"""

import logging

import pytest

from app.modules.workflow.agents.rag import ThreadRAGSearchError, ThreadScopedRAG
from tests.unit.workflow.thread_rag_fakes import ACME_CHAT, GLOBEX_CHAT, make_search_fail

RAG_LOGGER = "app.modules.workflow.agents.rag"
ACME_NOTE = "The Acme invoice number is 48213."
GLOBEX_NOTE = "The Globex invoice number is 77001."


@pytest.fixture
def thread_rag(thread_rag_backends):
    return ThreadScopedRAG()


async def _add_notes_to_both_chats(thread_rag: ThreadScopedRAG) -> None:
    await thread_rag.add_message(ACME_CHAT, ACME_NOTE, "acme-1")
    await thread_rag.add_message(GLOBEX_CHAT, GLOBEX_NOTE, "globex-1")


@pytest.mark.asyncio
async def test_retrieve_returns_the_matching_content_of_the_same_chat(thread_rag):
    await _add_notes_to_both_chats(thread_rag)

    results = await thread_rag.retrieve(ACME_CHAT, "what is the invoice number", top_k=5)

    assert [result["content"] for result in results] == [ACME_NOTE]
    assert results[0]["metadata"]["chat_id"] == ACME_CHAT
    assert results[0]["metadata"]["message_id"] == "acme-1"


@pytest.mark.asyncio
async def test_retrieve_returns_nothing_from_another_chat(thread_rag):
    await thread_rag.add_message(GLOBEX_CHAT, GLOBEX_NOTE, "globex-1")

    results = await thread_rag.retrieve(ACME_CHAT, "what is the invoice number", top_k=5)

    assert results == []


@pytest.mark.asyncio
async def test_retrieve_returns_the_best_matches_first_up_to_top_k(thread_rag):
    await thread_rag.add_message(ACME_CHAT, "Parking permits are renewed every month.", "acme-1")
    await thread_rag.add_message(ACME_CHAT, ACME_NOTE, "acme-2")
    await thread_rag.add_message(ACME_CHAT, "The invoice was paid in March.", "acme-3")

    results = await thread_rag.retrieve(ACME_CHAT, "invoice number", top_k=2)

    assert [result["metadata"]["message_id"] for result in results] == ["acme-2", "acme-3"]


@pytest.mark.parametrize(
    "top_k,expected_count",
    [(None, 5), ("5", 5), (0, 5), (-3, 5), ("many", 5), ("2", 2), (2.0, 2)],
)
@pytest.mark.asyncio
async def test_retrieve_uses_a_positive_whole_top_k_or_the_default(thread_rag, top_k, expected_count):
    for number in range(7):
        await thread_rag.add_message(ACME_CHAT, f"Acme invoice {number} was paid.", f"acme-{number}")

    results = await thread_rag.retrieve(ACME_CHAT, "invoice paid", top_k=top_k)

    assert len(results) == expected_count


@pytest.mark.asyncio
async def test_retrieve_raises_when_the_search_service_cannot_start(thread_rag, thread_rag_backends):
    embedder, _store = thread_rag_backends
    embedder.fail_initialize = True

    with pytest.raises(ThreadRAGSearchError, match="not available"):
        await thread_rag.retrieve(ACME_CHAT, "what is the invoice number")


@pytest.mark.asyncio
async def test_retrieve_raises_a_plain_error_and_logs_the_detail_when_the_search_raises(thread_rag, caplog):
    search_error = RuntimeError("search outage")
    await thread_rag.add_message(ACME_CHAT, ACME_NOTE, "acme-1")
    await make_search_fail(thread_rag, ACME_CHAT, search_error)

    with caplog.at_level(logging.ERROR, logger=RAG_LOGGER), pytest.raises(ThreadRAGSearchError) as raised:
        await thread_rag.retrieve(ACME_CHAT, "what is the invoice number")

    assert str(raised.value) == "Search failed for chat chat-acme"
    assert raised.value.__cause__ is search_error
    detail_lines = [record.getMessage() for record in caplog.records if "search outage" in record.getMessage()]
    assert detail_lines == ["Error retrieving from chat chat-acme: search outage"]


@pytest.mark.asyncio
async def test_failed_search_in_one_chat_leaves_the_other_chat_searchable(thread_rag):
    await _add_notes_to_both_chats(thread_rag)
    await make_search_fail(thread_rag, ACME_CHAT, RuntimeError("search outage"))

    globex_results = await thread_rag.retrieve(GLOBEX_CHAT, "what is the invoice number")

    assert [result["content"] for result in globex_results] == [GLOBEX_NOTE]


@pytest.mark.asyncio
async def test_purge_chat_removes_only_that_chat_and_does_not_search(thread_rag, thread_rag_backends):
    embedder, store = thread_rag_backends
    await _add_notes_to_both_chats(thread_rag)

    purge_result = await thread_rag.purge_chat(ACME_CHAT)

    assert purge_result == {"vector": True}
    assert store.contents_of_chat(ACME_CHAT) == []
    assert store.contents_of_chat(GLOBEX_CHAT) == [GLOBEX_NOTE]
    assert embedder.queries == []
    assert store.search_count == 0


@pytest.mark.asyncio
async def test_purged_chat_has_nothing_left_to_find(thread_rag):
    await _add_notes_to_both_chats(thread_rag)

    await thread_rag.purge_chat(ACME_CHAT)

    assert await thread_rag.retrieve(ACME_CHAT, "what is the invoice number") == []
    globex_results = await thread_rag.retrieve(GLOBEX_CHAT, "what is the invoice number")
    assert [result["content"] for result in globex_results] == [GLOBEX_NOTE]


@pytest.mark.asyncio
async def test_purge_chat_returns_nothing_when_the_service_cannot_start(thread_rag, thread_rag_backends):
    embedder, _store = thread_rag_backends
    embedder.fail_initialize = True

    assert await thread_rag.purge_chat(ACME_CHAT) == {}


@pytest.mark.asyncio
async def test_added_file_is_found_in_the_same_chat_only(thread_rag):
    await thread_rag.add_file_content(
        chat_id=ACME_CHAT,
        file_content="Acme premium plan costs 40 euros per month.",
        file_name="acme-pricing.txt",
        file_id="file-1",
    )

    results = await thread_rag.retrieve(ACME_CHAT, "premium plan cost")

    assert "Acme premium plan costs 40 euros per month." in results[0]["content"]
    assert results[0]["metadata"]["filename"] == "acme-pricing.txt"
    assert results[0]["metadata"]["message_id"] == "file_file-1"
    assert await thread_rag.retrieve(GLOBEX_CHAT, "premium plan cost") == []


@pytest.mark.asyncio
async def test_add_file_content_applies_the_config_overrides(thread_rag, thread_rag_backends):
    _embedder, store = thread_rag_backends
    long_text = " ".join(f"Acme clause {number} covers topic {number}." for number in range(60))

    await thread_rag.add_file_content(
        chat_id=ACME_CHAT,
        file_content=long_text,
        file_name="acme-contract.txt",
        file_id="file-2",
        config_overrides={"chunk_size": 200, "chunk_overlap": 0},
    )

    stored_chunks = store.contents_of_chat(ACME_CHAT)
    assert len(stored_chunks) > 5
    assert all(len(chunk) <= 200 for chunk in stored_chunks)
