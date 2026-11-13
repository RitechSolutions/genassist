"""A knowledge search that fails is reported as failed, from the vector store up to the run details."""

import asyncio
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.modules.data.config import AgentRAGConfig
from app.modules.data.manager import AgentRAGServiceManager
from app.modules.data.providers import KnowledgeSearchError, PlainProvider, SearchResult
from app.modules.data.providers.vector.db.base import SearchResult as StoreHit
from app.modules.data.providers.vector.db.base import VectorDBConfig
from app.modules.data.providers.vector.embedding import bedrock
from app.modules.data.providers.vector.embedding.base import EmbeddingConfig
from app.modules.data.providers.vector.embedding.bedrock import BedrockEmbedder
from app.modules.data.providers.vector.embedding.huggingface import HuggingFaceEmbedder
from app.modules.data.providers.vector.embedding.openai import OpenAIEmbedder
from app.modules.data.providers.vector.provider import VectorProvider
from app.modules.data.service import (
    FAILURE_REASON_MAX_LENGTH,
    FAILURE_TEXT_MAX_LENGTH,
    AgentRAGService,
    capped_failure_text,
    search_failure_reason,
)
from app.modules.data.utils.doc import format_search_results
from app.modules.workflow.engine.nodes.knowledge_tool_node import KnowledgeToolNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.schemas.agent_knowledge import KBRead
from app.services.agent_knowledge import KnowledgeBaseService

QUERY = "How do I reset my password?"
QUERY_VECTOR = [0.1, 0.2, 0.3, 0.4]
NODE_ID = "kb"
EMBEDDER_OUTAGE = RuntimeError("embedding model outage (ThrottlingException)")
STORE_OUTAGE = ConnectionError("vector database connection closed")
PASSWORD_ARTICLE = StoreHit(
    id="KB:1#content_chunk_0",
    content="Open Settings, then choose Reset password.",
    metadata={"doc_id": "KB:1#content", "name": "Password reset", "chunk_index": 0},
    score=0.81,
)


class FakeEmbedder:
    def __init__(self, error=None, starts=True, vector=QUERY_VECTOR):
        self.error = error
        self.starts = starts
        self.vector = vector

    async def initialize(self):
        return self.starts

    async def get_dimension(self):
        return len(QUERY_VECTOR)

    async def embed_query(self, query):
        if self.error:
            raise self.error
        return list(self.vector)


class FakeVectorStore:
    def __init__(self, hits=(), error=None):
        self.hits = list(hits)
        self.error = error

    async def initialize(self):
        return True

    async def create_collection(self, dimension):
        return True

    async def search(self, query_vector, limit, filter_dict=None):
        if self.error:
            raise self.error
        return self.hits[:limit]

    def close(self):
        pass


class FakeProvider:
    def __init__(self, name, results=(), error=None):
        self.name = name
        self.results = list(results)
        self.error = error

    async def search(self, query, limit, doc_ids=None):
        if self.error:
            raise self.error
        return [result.model_copy() for result in self.results]


class FailingClient:
    """Stands in for a provider SDK client whose call fails."""

    def __init__(self, error):
        self.error = error

    async def aembed_query(self, query):
        raise self.error

    async def query(self, **kwargs):
        raise self.error

    async def query_points(self, **kwargs):
        raise self.error

    def begin(self):
        raise self.error

    def search(self, *args):
        raise self.error


def _problem_lines(caplog):
    """Warnings and errors the application code logged, without those of imported libraries."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app.") and record.levelno >= logging.WARNING
    ]


def _bare(cls, **attributes):
    """An instance without its constructor, holding only what the method under test reads."""
    instance = object.__new__(cls)
    for name, value in attributes.items():
        setattr(instance, name, value)
    return instance


def _vector_provider(embedder=None, store=None):
    config = SimpleNamespace(
        embedding=SimpleNamespace(get=lambda: embedder or FakeEmbedder()),
        vector_db=SimpleNamespace(get=lambda: store or FakeVectorStore()),
        chunking=SimpleNamespace(get=lambda: None),
    )
    return VectorProvider(config, "kb-1")


def _result(result_id, score, source="vector"):
    return SearchResult(id=result_id, content=f"text of {result_id}", metadata={}, score=score, source=source)


def _service(*providers):
    service = AgentRAGService(AgentRAGConfig(knowledge_base_id="kb-1"))
    service.data_provider = list(providers)
    service._initialized = True
    return service


def _knowledge_base(name):
    return SimpleNamespace(id=uuid.uuid4(), name=name)


def _manager(services_by_name):
    manager = AgentRAGServiceManager()
    manager.get_service = AsyncMock(side_effect=lambda kb: services_by_name[kb.name])
    return manager


# ---- vector stores and embedders

def _failing_stores(error):
    from app.modules.data.providers.vector.db.chroma import ChromaVectorDB
    from app.modules.data.providers.vector.db.faiss import FaissVectorDB
    from app.modules.data.providers.vector.db.pgvector import PgVectorDB
    from app.modules.data.providers.vector.db.qdrant import QdrantVectorDB

    cosine = SimpleNamespace(distance_metric="cosine")
    client = FailingClient(error)
    return {
        "pgvector": _bare(PgVectorDB, engine=client, table_name="acme_vectors", dimension=4, config=cosine),
        "chroma": _bare(ChromaVectorDB, collection=client),
        "qdrant": _bare(QdrantVectorDB, client=client, collection_name="acme", config=cosine),
        "faiss": _bare(FaissVectorDB, index=SimpleNamespace(ntotal=1, search=client.search), config=cosine),
    }


def _uninitialized_stores():
    from app.modules.data.providers.vector.db.chroma import ChromaVectorDB
    from app.modules.data.providers.vector.db.pgvector import PgVectorDB
    from app.modules.data.providers.vector.db.qdrant import QdrantVectorDB

    return {
        "pgvector": _bare(PgVectorDB, engine=None, table_name=None, dimension=None),
        "chroma": _bare(ChromaVectorDB, collection=None),
        "qdrant": _bare(QdrantVectorDB, client=None),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("store_name", ["pgvector", "chroma", "qdrant", "faiss"])
async def test_vector_store_raises_when_its_search_fails(store_name):
    store = _failing_stores(STORE_OUTAGE)[store_name]

    with pytest.raises(ConnectionError, match="connection closed"):
        await store.search(QUERY_VECTOR, limit=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("store_name", ["pgvector", "chroma", "qdrant"])
async def test_vector_store_raises_when_it_is_not_initialized(store_name):
    store = _uninitialized_stores()[store_name]

    with pytest.raises(RuntimeError, match="not initialized"):
        await store.search(QUERY_VECTOR, limit=5)


@pytest.mark.asyncio
async def test_empty_faiss_index_still_returns_no_results():
    from app.modules.data.providers.vector.db.faiss import FaissVectorDB

    store = _bare(FaissVectorDB, index=SimpleNamespace(ntotal=0))

    assert await store.search(QUERY_VECTOR, limit=5) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embedder",
    [
        _bare(OpenAIEmbedder, client=FailingClient(EMBEDDER_OUTAGE)),
        _bare(HuggingFaceEmbedder, embeddings=FailingClient(EMBEDDER_OUTAGE)),
        _bare(BedrockEmbedder, client=FailingClient(EMBEDDER_OUTAGE)),
    ],
    ids=["openai", "huggingface", "bedrock"],
)
async def test_embedder_raises_when_the_query_embedding_fails(embedder):
    with pytest.raises(RuntimeError, match="ThrottlingException"):
        await embedder.embed_query(QUERY)


@pytest.mark.asyncio
async def test_bedrock_embedder_raises_when_every_attempt_times_out(monkeypatch):
    class SlowClient:
        async def aembed_query(self, query):
            await asyncio.sleep(5)

    monkeypatch.setattr(bedrock.settings, "BEDROCK_MAX_RETRY_QUERY_EMBEDDING", 1)
    monkeypatch.setattr(bedrock.settings, "BEDROCK_TIMEOUT_QUERY_EMBEDDING_SECONDS", 0.01)
    embedder = _bare(BedrockEmbedder, client=SlowClient())

    with pytest.raises(TimeoutError, match="did not answer within 0.01s"):
        await embedder.embed_query(QUERY)


# ---- providers

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embedder, store, reason",
    [
        (FakeEmbedder(error=EMBEDDER_OUTAGE), FakeVectorStore(), "ThrottlingException"),
        (FakeEmbedder(), FakeVectorStore(error=STORE_OUTAGE), "connection closed"),
        (FakeEmbedder(starts=False), FakeVectorStore(), "could not be started"),
        (FakeEmbedder(vector=[]), FakeVectorStore(), "returned no vector"),
    ],
    ids=["embedder raises", "store raises", "embedder cannot start", "embedder returns nothing"],
)
async def test_vector_provider_raises_when_the_search_fails(embedder, store, reason):
    provider = _vector_provider(embedder, store)

    with pytest.raises(Exception, match=reason):
        await provider.search(QUERY, limit=5)


@pytest.mark.asyncio
async def test_vector_provider_returns_an_empty_list_when_nothing_matches():
    provider = _vector_provider(FakeEmbedder(), FakeVectorStore(hits=[]))

    assert await provider.search(QUERY, limit=5) == []
    assert await provider.search("   ", limit=5) == []


@pytest.mark.asyncio
async def test_vector_provider_returns_the_matching_documents():
    provider = _vector_provider(FakeEmbedder(), FakeVectorStore(hits=[PASSWORD_ARTICLE]))

    results = await provider.search(QUERY, limit=5)

    assert [(result.id, result.score, result.source) for result in results] == [("KB:1#content", 0.81, "vector")]


@pytest.mark.asyncio
async def test_plain_provider_search_is_unchanged():
    provider = PlainProvider("kb-1")
    assert await provider.search(QUERY) == []

    await provider.add_document("KB:1#content", "Open Settings, then choose Reset password.")
    assert [result.id for result in await provider.search(QUERY)] == ["KB:1#content"]


def _legra_provider(monkeypatch, load):
    from app.modules.data.providers.legra import provider as legra_provider

    monkeypatch.setattr(legra_provider.Legra, "load", load)
    return _bare(legra_provider.LegraProvider, _initialized=True, legra_instance=object(), knowledge_base_id="kb-1")


@pytest.mark.asyncio
async def test_legra_provider_without_an_index_returns_no_results(monkeypatch, caplog):
    missing_index = MagicMock(side_effect=FileNotFoundError("legra_data/kb-1/docs_meta.json"))
    provider = _legra_provider(monkeypatch, missing_index)

    with caplog.at_level(logging.WARNING):
        results = await provider.search(QUERY)

    assert results == []
    assert _problem_lines(caplog) == ["LEGRA index of KB kb-1 not found, returning no results"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "load",
    [
        MagicMock(side_effect=ValueError("index is corrupt")),
        MagicMock(return_value=SimpleNamespace(query=MagicMock(side_effect=ValueError("index is corrupt")))),
    ],
    ids=["index unreadable", "query fails"],
)
async def test_legra_provider_raises_when_its_index_cannot_be_read_or_queried(monkeypatch, load):
    provider = _legra_provider(monkeypatch, load)

    with pytest.raises(ValueError, match="index is corrupt"):
        await provider.search(QUERY)


@pytest.mark.asyncio
async def test_lightrag_provider_raises_when_its_query_fails():
    from app.modules.data.providers.lightrag.provider import LightRAGProvider

    config = SimpleNamespace(search_mode="hybrid", top_k=5, response_type="Multiple Paragraphs")
    failing_rag = SimpleNamespace(aquery=AsyncMock(side_effect=STORE_OUTAGE))
    provider = _bare(LightRAGProvider, _initialized=True, rag=failing_rag, config=config, knowledge_base_id="kb-1")

    with pytest.raises(ConnectionError, match="connection closed"):
        await provider.search(QUERY)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_path", ["legra.provider.LegraProvider", "lightrag.provider.LightRAGProvider"])
async def test_graph_provider_that_is_not_initialized_raises(provider_path):
    import importlib

    module_path, class_name = provider_path.rsplit(".", 1)
    provider_class = getattr(importlib.import_module(f"app.modules.data.providers.{module_path}"), class_name)
    provider = _bare(provider_class, _initialized=False, legra_instance=None, rag=None)

    with pytest.raises(KnowledgeSearchError, match="is not initialized"):
        await provider.search(QUERY)


# ---- service: the providers of one knowledge base

@pytest.mark.asyncio
async def test_service_returns_merged_results_when_every_provider_answers():
    service = _service(FakeProvider("vector", [_result("a", 0.9)]), FakeProvider("legra", [_result("b", 0.5)]))

    assert [result.id for result in await service.search(QUERY, limit=5)] == ["a", "b"]


@pytest.mark.asyncio
async def test_service_returns_an_empty_list_when_no_provider_finds_anything():
    service = _service(FakeProvider("vector"), FakeProvider("legra"))

    assert await service.search(QUERY, limit=5) == []


@pytest.mark.asyncio
async def test_service_reports_a_failed_provider_and_keeps_the_results_of_the_others():
    service = _service(FakeProvider("vector", [_result("a", 0.9)]), FakeProvider("legra", error=STORE_OUTAGE))

    with pytest.raises(KnowledgeSearchError) as raised:
        await service.search(QUERY, limit=5)

    assert str(raised.value) == "legra search failed: vector database connection closed"
    assert [result.id for result in raised.value.results] == ["a"]
    assert raised.value.error_types == ["ConnectionError"]


@pytest.mark.asyncio
async def test_service_that_is_not_initialized_raises():
    service = AgentRAGService(AgentRAGConfig(knowledge_base_id="kb-1"))

    with pytest.raises(KnowledgeSearchError, match="not ready for search"):
        await service.search(QUERY, limit=5)


def test_failure_reason_is_one_short_line_without_secrets():
    error = RuntimeError(
        "could not connect to postgresql://acme_user:hunter2@localhost:5432/core_db\n"
        "api_key=sk-acme-0123456789abcdef0123456789abcdef " + "x" * 600
    )

    reason = search_failure_reason(error)

    assert "hunter2" not in reason
    assert "sk-acme-0123456789abcdef0123456789abcdef" not in reason
    assert "postgresql://***@localhost:5432/core_db" in reason
    assert "\n" not in reason
    assert len(reason) <= FAILURE_REASON_MAX_LENGTH


@pytest.mark.parametrize(
    "url, masked",
    [
        ("redis://user:pa/ss@host", "redis://***@host"),
        ("postgresql://user:p@ss@host:5432/core_db", "postgresql://***@host:5432/core_db"),
        ("amqp://user:p@/ss@host", "amqp://***@host"),
        ("redis://user:pa ss@host", "redis://***@host"),
        ("redis://user:pa ss/w@rd@host:6379/0", "redis://***@host:6379/0"),
        ("https://host/path", "https://host/path"),
    ],
)
def test_failure_reason_masks_url_passwords_that_hold_a_slash_an_at_sign_or_a_space(url, masked):
    assert search_failure_reason(RuntimeError(f"could not connect to {url} in time")) == (
        f"could not connect to {masked} in time"
    )


def test_failure_text_is_capped_as_a_whole():
    short_text = "vector search failed: connection closed"
    long_text = "x" * (FAILURE_TEXT_MAX_LENGTH + 200)

    assert capped_failure_text(short_text) == short_text
    assert capped_failure_text(long_text).startswith("x" * FAILURE_TEXT_MAX_LENGTH + "...")
    assert len(capped_failure_text(long_text)) < FAILURE_TEXT_MAX_LENGTH + 30


def test_failure_reason_falls_back_to_the_error_type():
    assert search_failure_reason(TimeoutError()) == "TimeoutError"


# ---- manager: several knowledge bases

@pytest.mark.asyncio
async def test_manager_search_is_unchanged_when_every_knowledge_base_answers():
    acme, globex = _knowledge_base("Acme help centre"), _knowledge_base("Globex policies")
    manager = _manager({
        "Acme help centre": _service(FakeProvider("vector", [_result("a", 0.4)])),
        "Globex policies": _service(FakeProvider("vector", [_result("b", 0.9)])),
    })

    results = await manager.search([acme, globex], QUERY, limit=5)

    assert [result.id for result in results] == ["b", "a"]


@pytest.mark.asyncio
async def test_manager_search_without_matches_keeps_the_no_results_text():
    acme = _knowledge_base("Acme help centre")
    manager = _manager({"Acme help centre": _service(FakeProvider("vector"))})

    assert await manager.search([acme], QUERY) == []
    assert await manager.search([acme], QUERY, format_results=True) == "No results found."


@pytest.mark.asyncio
async def test_manager_reports_the_failed_knowledge_base_and_keeps_the_results_of_the_others():
    acme, globex = _knowledge_base("Acme help centre"), _knowledge_base("Globex policies")
    manager = _manager({
        "Acme help centre": _service(FakeProvider("vector", [_result("a", 0.4)])),
        "Globex policies": _service(FakeProvider("vector", error=EMBEDDER_OUTAGE)),
    })

    with pytest.raises(KnowledgeSearchError) as raised:
        await manager.search([acme, globex], QUERY, limit=5)

    assert str(raised.value) == (
        'Search failed for knowledge base "Globex policies": '
        "vector search failed: embedding model outage (ThrottlingException)"
    )
    assert [result.id for result in raised.value.results] == ["a"]


@pytest.mark.asyncio
async def test_manager_keeps_the_other_results_when_a_knowledge_base_fails_unexpectedly():
    acme, globex = _knowledge_base("Acme help centre"), _knowledge_base("Globex policies")
    broken_service = SimpleNamespace(search=AsyncMock(side_effect=TypeError("unexpected store answer")))
    manager = _manager({
        "Acme help centre": broken_service,
        "Globex policies": _service(FakeProvider("vector", [_result("b", 0.9)])),
    })

    with pytest.raises(KnowledgeSearchError) as raised:
        await manager.search([acme, globex], QUERY, limit=5)

    assert str(raised.value) == 'Search failed for knowledge base "Acme help centre": unexpected store answer'
    assert [result.id for result in raised.value.results] == ["b"]
    assert raised.value.error_types == ["TypeError"]


@pytest.mark.asyncio
async def test_manager_reports_a_knowledge_base_whose_search_cannot_start():
    acme = _knowledge_base("Acme help centre")
    manager = _manager({"Acme help centre": None})

    with pytest.raises(KnowledgeSearchError, match='"Acme help centre": its search could not be started') as raised:
        await manager.search([acme], QUERY)

    assert raised.value.results == []


# ---- search route

@pytest.mark.asyncio
async def test_search_route_returns_the_results_of_the_knowledge_bases_that_answered():
    from app.api.v1.routes.agent_knowledge import search as search_route

    acme, globex = _knowledge_base("Acme help centre"), _knowledge_base("Globex policies")
    manager = _manager({
        "Acme help centre": _service(FakeProvider("vector", [_result("a", 0.4)])),
        "Globex policies": _service(FakeProvider("vector", error=STORE_OUTAGE)),
    })

    answer = await search_route(query=QUERY, items=[acme, globex], rag_manager=manager)

    assert answer == format_search_results([_result("a", 0.4)], include_metadata=False)


@pytest.mark.asyncio
async def test_search_route_answers_with_the_reason_when_the_search_fails():
    from app.api.v1.routes.agent_knowledge import search as search_route

    acme = _knowledge_base("Acme help centre")
    manager = _manager({"Acme help centre": _service(FakeProvider("vector", error=STORE_OUTAGE))})

    with pytest.raises(HTTPException) as raised:
        await search_route(query=QUERY, items=[acme], rag_manager=manager)

    assert raised.value.status_code == 500
    assert raised.value.detail == (
        'Knowledge search failed: Search failed for knowledge base "Acme help centre": '
        "vector search failed: vector database connection closed"
    )


# ---- run details: the knowledge step on the real manager, service and vector provider

def _use_fake_backends(monkeypatch, embedder, store):
    monkeypatch.setattr(EmbeddingConfig, "get", lambda self: embedder)
    monkeypatch.setattr(VectorDBConfig, "get", lambda self: store)


async def _run_knowledge_step(knowledge_bases):
    """Run the step on the real search stack; returns what it returned and its run entry."""
    selected_ids = [str(knowledge_base.id) for knowledge_base in knowledge_bases]
    node_config = {
        "id": NODE_ID,
        "type": "knowledgeBaseNode",
        "data": {"name": "Help centre search", "selectedBases": selected_ids, "query": QUERY, "limit": 5},
    }
    state = WorkflowState(workflow={"nodes": [node_config], "config": {}}, thread_id=str(uuid.uuid4()))
    knowledge_service = MagicMock(get_by_ids=AsyncMock(return_value=list(knowledge_bases)))
    manager = AgentRAGServiceManager()
    injector = MagicMock(get=lambda cls: knowledge_service if cls is KnowledgeBaseService else manager)
    with patch("app.dependencies.injector.injector", injector):
        returned = await KnowledgeToolNode(NODE_ID, node_config, state).execute()
    return returned, state.node_execution_status[NODE_ID]


def _vector_knowledge_base(name="Acme help centre"):
    return KBRead(id=uuid.uuid4(), name=name, type="text", rag_config={"enabled": True, "vector": {"enabled": True}})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embedder, store, reason",
    [
        (FakeEmbedder(error=EMBEDDER_OUTAGE), FakeVectorStore(), "embedding model outage (ThrottlingException)"),
        (FakeEmbedder(), FakeVectorStore(error=STORE_OUTAGE), "vector database connection closed"),
        (FakeEmbedder(starts=False), FakeVectorStore(), "its search could not be started"),
    ],
    ids=["embedder raises", "store raises", "embedder cannot start"],
)
async def test_run_details_show_a_failed_search_as_failed_with_the_reason(monkeypatch, embedder, store, reason):
    _use_fake_backends(monkeypatch, embedder, store)

    returned, entry = await _run_knowledge_step([_vector_knowledge_base()])

    assert returned["__node_failed__"] is True
    assert entry["status"] == "failed"
    assert 'Search failed for knowledge base "Acme help centre"' in entry["error"]
    assert reason in entry["error"]


@pytest.mark.asyncio
async def test_run_details_show_an_empty_search_as_a_success_with_no_results(monkeypatch):
    _use_fake_backends(monkeypatch, FakeEmbedder(), FakeVectorStore(hits=[]))

    returned, entry = await _run_knowledge_step([_vector_knowledge_base()])

    assert returned == "No results found."
    assert entry["status"] == "success"
    assert entry["error"] is None
    assert entry["sources"] == []
    assert "warnings" not in entry


@pytest.mark.asyncio
async def test_run_details_show_a_search_that_found_an_article_as_before(monkeypatch):
    _use_fake_backends(monkeypatch, FakeEmbedder(), FakeVectorStore(hits=[PASSWORD_ARTICLE]))

    returned, entry = await _run_knowledge_step([_vector_knowledge_base()])

    assert returned.startswith("Found 1 results:")
    assert entry["status"] == "success"
    assert [source["title"] for source in entry["sources"]] == ["Password reset"]


@pytest.mark.asyncio
async def test_a_failed_search_writes_one_error_line_with_the_masked_reason_and_error_type(monkeypatch, caplog):
    outage = ConnectionError("could not reach postgresql://acme_user:hunter2@db-host:5432/core_db")
    _use_fake_backends(monkeypatch, FakeEmbedder(), FakeVectorStore(error=outage))

    with caplog.at_level(logging.WARNING):
        _, entry = await _run_knowledge_step([_vector_knowledge_base()])

    assert _problem_lines(caplog) == [
        'Error processing knowledge tool: Search failed for knowledge base "Acme help centre": '
        "vector search failed: could not reach postgresql://***@db-host:5432/core_db [ConnectionError]"
    ]
    assert "hunter2" not in caplog.text
    assert "hunter2" not in str(entry)
