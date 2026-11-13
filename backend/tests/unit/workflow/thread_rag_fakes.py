"""Fake embedder and vector store for tests of the search within one chat"""

import re
import zlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.modules.data.providers.vector.db.base import SearchResult, VectorDBConfig
from app.modules.data.providers.vector.embedding.base import EmbeddingConfig

DIMENSION = 256
ACME_CHAT = "chat-acme"
GLOBEX_CHAT = "chat-globex"


def _word_vector(text: str) -> List[float]:
    """Count each word into a fixed slot, so texts sharing words get close vectors."""
    vector = [0.0] * DIMENSION
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        vector[zlib.crc32(word.encode()) % DIMENSION] += 1.0
    return vector


def _cosine_similarity(first: List[float], second: List[float]) -> float:
    norms = float(np.linalg.norm(first) * np.linalg.norm(second))
    return float(np.dot(first, second)) / norms if norms else 0.0


class FakeEmbedder:
    """Stands in for a model provider; can be told to fail at start-up."""

    def __init__(self):
        self.fail_initialize = False
        self.queries: List[str] = []

    async def initialize(self) -> bool:
        return not self.fail_initialize

    async def get_dimension(self) -> int:
        return DIMENSION

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [_word_vector(text) for text in texts]

    async def embed_query(self, query: str) -> List[float]:
        self.queries.append(query)
        return _word_vector(query)


class FakeVectorStore:
    """One in-memory store shared by every chat, so only the metadata filter keeps chats apart."""

    def __init__(self):
        self.rows: Dict[str, Dict[str, Any]] = {}
        self.search_count = 0

    async def initialize(self) -> bool:
        return True

    async def create_collection(self, dimension: int) -> bool:
        return True

    async def add_vectors(self, ids, vectors, metadatas, contents) -> bool:
        for row_id, vector, metadata, content in zip(ids, vectors, metadatas, contents):
            self.rows[row_id] = {"vector": vector, "metadata": dict(metadata), "content": content}
        return True

    async def delete_vectors_by_metadata(self, filter_dict: Dict[str, Any]) -> bool:
        matching_ids = [row_id for row_id, row in self.rows.items() if self._matches(row, filter_dict)]
        for row_id in matching_ids:
            del self.rows[row_id]
        return True

    async def search(self, query_vector, limit: int = 5, filter_dict=None) -> List[SearchResult]:
        self.search_count += 1
        scored = [
            (_cosine_similarity(query_vector, row["vector"]), row_id, row)
            for row_id, row in self.rows.items()
            if self._matches(row, filter_dict)
        ]
        relevant = [entry for entry in scored if entry[0] > 0]
        relevant.sort(key=lambda entry: entry[0], reverse=True)
        return [
            SearchResult(id=row_id, content=row["content"], metadata=dict(row["metadata"]), score=min(score, 1.0))
            for score, row_id, row in relevant[:limit]
        ]

    def contents_of_chat(self, chat_id: str) -> List[str]:
        return [row["content"] for row in self.rows.values() if row["metadata"].get("chat_id") == chat_id]

    def close(self) -> None:
        pass

    @staticmethod
    def _matches(row: Dict[str, Any], filter_dict: Optional[Dict[str, Any]]) -> bool:
        return all(str(row["metadata"].get(key)) == str(value) for key, value in (filter_dict or {}).items())


class FailingSearchService:
    """A chat's search service whose search always raises; everything else works as usual."""

    def __init__(self, service, error: Exception):
        self._service = service
        self._error = error

    def __getattr__(self, name: str):
        return getattr(self._service, name)

    async def search(self, *args, **kwargs):
        raise self._error


async def make_search_fail(thread_rag, chat_id: str, error: Exception) -> None:
    """From now on every search in this chat raises the given error."""
    service = await thread_rag._get_service(chat_id)
    thread_rag._services[chat_id] = FailingSearchService(service, error)


def install_fake_backends(monkeypatch) -> Tuple[FakeEmbedder, FakeVectorStore]:
    """Every per-chat search service built in the test uses the fakes, never a provider or a database."""
    embedder = FakeEmbedder()
    store = FakeVectorStore()
    monkeypatch.setattr(EmbeddingConfig, "get", lambda self: embedder)
    monkeypatch.setattr(VectorDBConfig, "get", lambda self: store)
    return embedder, store
