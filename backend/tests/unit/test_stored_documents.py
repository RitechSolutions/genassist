"""A knowledge base's stored documents are read back with their whole text."""
from types import SimpleNamespace

import pytest

from app.modules.data.providers.base import BaseDataProvider
from app.modules.data.providers.models import StoredDocument
from app.modules.data.providers.vector.provider import VectorProvider
from app.modules.data.providers.vector.stored_documents import joined_document, pieces_by_document
from app.modules.data.service import AgentRAGService


def piece(piece_id, content, name="Lock the bike"):
    return SimpleNamespace(id=piece_id, content=content, metadata={"name": name})


class FakeVectorDB:
    def __init__(self, pieces):
        self.pieces = {stored.id: stored for stored in pieces}
        self.filters = []

    async def get_all_ids(self, filter_dict=None):
        self.filters.append(filter_dict)
        return list(self.pieces)

    async def get_by_ids(self, ids):
        return [self.pieces[piece_id] for piece_id in reversed(ids) if piece_id in self.pieces]


def vector_provider(pieces):
    provider = object.__new__(VectorProvider)
    provider._initialized = True
    provider.knowledge_base_id = "kb-1"
    provider.vector_db = FakeVectorDB(pieces)
    return provider


class TestPieces:
    def test_pieces_are_grouped_by_document_in_reading_order(self):
        ids = ["doc-a_chunk_10", "doc-b_chunk_0", "doc-a_chunk_2", "doc-a_chunk_0"]
        assert pieces_by_document(ids) == {
            "doc-a": ["doc-a_chunk_0", "doc-a_chunk_2", "doc-a_chunk_10"],
            "doc-b": ["doc-b_chunk_0"],
        }

    def test_a_document_whose_own_name_holds_the_mark_keeps_its_name(self):
        ids = ["docs/report_chunk_1.pdf_chunk_0", "docs/report_chunk_2.pdf_chunk_0", "docs/report_chunk_1.pdf_chunk_1"]
        assert pieces_by_document(ids) == {
            "docs/report_chunk_1.pdf": ["docs/report_chunk_1.pdf_chunk_0", "docs/report_chunk_1.pdf_chunk_1"],
            "docs/report_chunk_2.pdf": ["docs/report_chunk_2.pdf_chunk_0"],
        }

    def test_a_document_is_its_pieces_joined_in_order_under_the_shown_name(self):
        pieces = [piece("doc-a_chunk_1", "Push the ring lock down."), piece("doc-a_chunk_0", "Lock the bike")]
        document = joined_document("doc-a", pieces)
        assert document == StoredDocument(id="doc-a", title="Lock the bike", content="Lock the bike\nPush the ring lock down.")

    def test_a_document_without_a_name_has_no_title(self):
        assert joined_document("doc-a", [piece("doc-a_chunk_0", "Text", name=None)]).title is None


class TestReadingBack:
    @pytest.mark.asyncio
    async def test_the_vector_provider_returns_every_document_of_its_knowledge_base(self):
        provider = vector_provider([
            piece("doc-a_chunk_0", "Lock the bike"), piece("doc-a_chunk_1", "Push the ring lock down."),
            piece("doc-b_chunk_0", "Pay for a ride", name="Pay for a ride"),
        ])
        documents = await provider.get_documents()
        assert [(document.id, document.title) for document in documents] == [
            ("doc-a", "Lock the bike"), ("doc-b", "Pay for a ride"),
        ]
        assert documents[0].content == "Lock the bike\nPush the ring lock down."
        assert provider.vector_db.filters == [{"kb_id": "kb-1"}]

    @pytest.mark.asyncio
    async def test_a_provider_that_cannot_give_its_text_back_returns_none(self):
        assert await BaseDataProvider.get_documents(SimpleNamespace()) == []

    @pytest.mark.asyncio
    async def test_the_service_answers_from_the_first_provider_that_has_the_text(self):
        document = StoredDocument(id="doc-a", title="Lock the bike", content="Lock the bike")

        async def none():
            return []

        async def some():
            return [document]

        service = object.__new__(AgentRAGService)
        service._initialized = True
        service.data_provider = [SimpleNamespace(get_documents=none), SimpleNamespace(get_documents=some)]
        assert await service.get_documents() == [document]
