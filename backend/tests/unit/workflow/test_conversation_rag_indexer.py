"""Tests for the RAG Retrieval memory mode: the context an agent gets from ConversationRAGIndexer"""

import logging

import pytest

from app.modules.workflow.agents.conversation_rag_indexer import ConversationRAGIndexer
from app.modules.workflow.agents.memory import InMemoryConversationMemory
from app.modules.workflow.agents.rag import ThreadScopedRAG
from tests.unit.workflow.thread_rag_fakes import ACME_CHAT, GLOBEX_CHAT, make_search_fail

INDEXER_LOGGER = "app.modules.workflow.agents.conversation_rag_indexer"
RETRIEVED_BLOCK_TYPE = "rag_retrieved_history"
TOPICS = [
    "parking", "refunds", "invoices", "permits", "zones", "fines", "tickets", "billing", "accounts", "passwords",
    "cards", "receipts", "vouchers", "discounts", "garages", "meters", "plates", "vehicles", "badges", "sensors",
]
RECENT_MESSAGES = 6
ORDER_TURN = 1
QUESTION = "what was my order number?"


@pytest.fixture
def indexer(thread_rag_backends):
    return ConversationRAGIndexer(
        thread_rag=ThreadScopedRAG(),
        passthrough_threshold=30,
        recent_messages=RECENT_MESSAGES,
        top_k=3,
        rag_config_overrides={"chunk_size": 100_000, "chunk_overlap": 0},
    )


async def _long_chat(chat_id: str, order_number: str) -> InMemoryConversationMemory:
    memory = InMemoryConversationMemory(chat_id)
    for turn, topic in enumerate(TOPICS):
        order_note = f" My order number is {order_number}." if turn == ORDER_TURN else ""
        await memory.add_user_message(f"Please explain {topic}.{order_note}")
        await memory.add_assistant_message(f"Here is how {topic} works.")
    return memory


def _retrieved_blocks(context) -> list:
    return [message for message in context if message.get("message_type") == RETRIEVED_BLOCK_TYPE]


async def _recent_messages(memory: InMemoryConversationMemory) -> list:
    total = await memory.get_total_message_count()
    return await memory.get_messages_by_range(total - RECENT_MESSAGES, total)


@pytest.mark.asyncio
async def test_context_starts_with_the_matching_earlier_messages(indexer):
    memory = await _long_chat(ACME_CHAT, "48213")

    context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    assert context[0]["role"] == "system"
    assert context[0]["message_type"] == RETRIEVED_BLOCK_TYPE
    assert "My order number is 48213." in context[0]["content"]
    assert context[1:] == await _recent_messages(memory)


@pytest.mark.asyncio
async def test_context_never_holds_messages_of_another_chat(indexer):
    acme_memory = await _long_chat(ACME_CHAT, "48213")
    globex_memory = await _long_chat(GLOBEX_CHAT, "77001")
    await indexer.assemble_context(GLOBEX_CHAT, globex_memory, QUESTION)

    context = await indexer.assemble_context(ACME_CHAT, acme_memory, QUESTION)

    retrieved_text = _retrieved_blocks(context)[0]["content"]
    assert "48213" in retrieved_text
    assert "77001" not in retrieved_text


@pytest.mark.asyncio
async def test_failed_search_keeps_the_recent_messages_and_logs_an_error(indexer, caplog):
    memory = await _long_chat(ACME_CHAT, "48213")
    await make_search_fail(indexer.thread_rag, ACME_CHAT, RuntimeError("search outage"))

    with caplog.at_level(logging.ERROR, logger=INDEXER_LOGGER):
        context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    assert context == await _recent_messages(memory)
    indexer_errors = [record.getMessage() for record in caplog.records if record.name == INDEXER_LOGGER]
    assert any(
        message.endswith("retrieve failed for thread chat-acme: Search failed for chat chat-acme")
        for message in indexer_errors
    )


@pytest.mark.asyncio
async def test_unavailable_search_service_keeps_the_recent_messages_and_logs_an_error(indexer, thread_rag_backends, caplog):
    embedder, _store = thread_rag_backends
    memory = await _long_chat(ACME_CHAT, "48213")
    embedder.fail_initialize = True

    with caplog.at_level(logging.ERROR, logger=INDEXER_LOGGER):
        context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    assert context == await _recent_messages(memory)
    indexer_errors = [record.getMessage() for record in caplog.records if record.name == INDEXER_LOGGER]
    assert any("Search service is not available for chat chat-acme" in message for message in indexer_errors)


@pytest.mark.asyncio
async def test_short_chat_passes_all_messages_without_searching(indexer, thread_rag_backends):
    embedder, store = thread_rag_backends
    memory = InMemoryConversationMemory(ACME_CHAT)
    await memory.add_user_message("My order number is 48213.")
    await memory.add_assistant_message("Thank you.")

    context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    assert [message["content"] for message in context] == ["My order number is 48213.", "Thank you."]
    assert embedder.queries == []
    assert store.rows == {}


class RecordingThreadRAG:
    """Stands in for ThreadScopedRAG: records each search and answers with fixed groups per search text."""

    def __init__(self, groups, context_groups=None, context_error=None):
        self.groups = groups
        self.context_groups = context_groups
        self.context_error = context_error
        self.searches = []

    async def retrieve(self, chat_id, query, top_k, config_overrides=None):
        self.searches.append({"query": query, "top_k": top_k})
        is_context_search = query != QUESTION
        if is_context_search and self.context_error:
            raise self.context_error
        if is_context_search and self.context_groups is not None:
            return self.context_groups[:top_k]
        return self.groups[:top_k]


def _group(start: int, text: str) -> dict:
    return {"content": text, "metadata": {"group_start": start, "group_end": start + 4}}


def _recording_indexer(groups, context_groups=None, context_error=None, **settings) -> ConversationRAGIndexer:
    return ConversationRAGIndexer(
        thread_rag=RecordingThreadRAG(groups, context_groups, context_error), passthrough_threshold=30,
        recent_messages=RECENT_MESSAGES, top_k=3, **settings,
    )


@pytest.mark.asyncio
async def test_the_message_alone_is_searched_first_then_with_recent_context(thread_rag_backends):
    indexer = _recording_indexer([_group(0, "My order number is 48213.")])
    memory = await _long_chat(ACME_CHAT, "48213")

    await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    queries = [search["query"] for search in indexer.thread_rag.searches]
    assert queries[0] == QUESTION
    assert "User: Please explain sensors." in queries[1] and queries[1].endswith(f"User: {QUESTION}")
    assert all(search["top_k"] > 3 for search in indexer.thread_rag.searches)


@pytest.mark.asyncio
async def test_groups_already_in_the_recent_messages_do_not_take_the_places(thread_rag_backends):
    recent_groups = [_group(36, "recent talk A"), _group(34, "recent talk B")]
    older_groups = [_group(0, "older one"), _group(10, "older two"), _group(20, "older three"), _group(26, "older four")]
    indexer = _recording_indexer(recent_groups + older_groups)
    memory = await _long_chat(ACME_CHAT, "48213")

    context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    retrieved_text = _retrieved_blocks(context)[0]["content"]
    assert all(text in retrieved_text for text in ("older one", "older two", "older three"))
    assert "older four" not in retrieved_text
    assert "recent talk" not in retrieved_text


@pytest.mark.asyncio
async def test_a_group_found_by_both_searches_appears_once(thread_rag_backends):
    indexer = _recording_indexer([_group(0, "My order number is 48213.")])
    memory = await _long_chat(ACME_CHAT, "48213")

    context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    assert _retrieved_blocks(context)[0]["content"].count("My order number is 48213.") == 1


@pytest.mark.asyncio
async def test_without_recent_context_only_the_message_is_searched(thread_rag_backends):
    indexer = _recording_indexer([_group(0, "My order number is 48213.")], query_context_messages=0)
    memory = await _long_chat(ACME_CHAT, "48213")

    await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    assert [search["query"] for search in indexer.thread_rag.searches] == [QUESTION]


@pytest.mark.asyncio
async def test_old_fact_is_found_after_a_long_unrelated_talk(thread_rag_backends):
    indexer = ConversationRAGIndexer(
        thread_rag=ThreadScopedRAG(), passthrough_threshold=30, recent_messages=RECENT_MESSAGES, top_k=3,
        rag_config_overrides={"chunk_size": 100_000, "chunk_overlap": 0},
    )
    memory = InMemoryConversationMemory(ACME_CHAT)
    await memory.add_user_message("My booking reference is GLX-4471.")
    await memory.add_assistant_message("Noted.")
    for turn in range(19):
        await memory.add_user_message(f"Tell me something about bike number {turn} and its frame sticker.")
        await memory.add_assistant_message(f"Bike number {turn} has a sticker on the frame.")

    context = await indexer.assemble_context(ACME_CHAT, memory, "What booking reference did I give you?")

    assert "GLX-4471" in _retrieved_blocks(context)[0]["content"]


@pytest.mark.asyncio
async def test_each_search_contributes_in_turns(thread_rag_backends):
    message_groups = [_group(0, "message match one"), _group(4, "message match two"), _group(8, "message match three")]
    context_groups = [_group(12, "context match one"), _group(16, "context match two")]
    indexer = _recording_indexer(message_groups, context_groups=context_groups)
    memory = await _long_chat(ACME_CHAT, "48213")

    context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    retrieved_text = _retrieved_blocks(context)[0]["content"]
    assert all(text in retrieved_text for text in ("message match one", "context match one", "message match two"))
    assert "message match three" not in retrieved_text and "context match two" not in retrieved_text
    assert retrieved_text.index("message match one") < retrieved_text.index("context match one")


@pytest.mark.asyncio
async def test_one_failed_search_keeps_the_other_results_and_logs_an_error(thread_rag_backends, caplog):
    indexer = _recording_indexer([_group(0, "My order number is 48213.")], context_error=RuntimeError("timeout"))
    memory = await _long_chat(ACME_CHAT, "48213")

    with caplog.at_level(logging.ERROR, logger=INDEXER_LOGGER):
        context = await indexer.assemble_context(ACME_CHAT, memory, QUESTION)

    assert "My order number is 48213." in _retrieved_blocks(context)[0]["content"]
    assert any("one search failed for thread chat-acme: timeout" in record.getMessage() for record in caplog.records)
