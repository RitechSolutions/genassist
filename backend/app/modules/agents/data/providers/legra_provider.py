
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.modules.agents.data.providers.i_data_source_provider import DataSourceProvider
from app.modules.legra import FaissFlatIndexer, HuggingFaceGenerator, Legra, LeidenClusterer, SemanticChunker, \
    SentenceTransformerEmbedder


_logger = logging.getLogger(__name__)


class LegraProvider(DataSourceProvider):

    def __init__(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cluster_resolution: float = 0.5,
        generator_model_name: str = "gpt2",
        use_gpu: bool = False,
        max_tokens=1024,
    ):
        super().__init__()

        # Build the Legra stack once; keep it in memory
        chunker   = SemanticChunker(min_sents=1, max_sents=30, min_sent_length=32)

        embedder  = SentenceTransformerEmbedder(model_name=embedding_model_name)
        indexer   = FaissFlatIndexer(dim=embedder.dimension, use_gpu=use_gpu)

        clusterer = LeidenClusterer(resolution_parameter=cluster_resolution)
        generator = HuggingFaceGenerator(
            model_name=generator_model_name,
            device="cuda" if use_gpu else "cpu",
            truncate_context_size=1024,
        )
        self.rag = Legra(
            doc_folder="",               # we load files from memory, not disk
            chunker=chunker,
            embedder=embedder,
            indexer=indexer,
            clusterer=clusterer,
            generator=generator,
            max_tokens=max_tokens,
        )

        # In-memory index starts empty.
        self._indexed = False

    def initialize(self) -> bool:
        """Initialize the data source connection"""
        pass


    async def add_document(
        self, doc_id: str, content: str, metadata: Dict[str, Any]
    ) -> bool:
        """
        Add / replace one document.
        • We first delete (if it exists) so this becomes idempotent.
        • Then we call ` Legra.add()`, which appends vectors and refreshes the
          graph & clusters.
        """

        try:

            self.rag.add_document(doc_id, extracted_text=content, metadata=metadata)

            _logger.info(f"LegraProvider: added {doc_id}")
            return True

        except Exception as e:
            _logger.exception(f"LegraProvider: add_document failed for {doc_id}: {e}")
            return False

    async def delete_document(self, doc_id: str) -> bool:
        """
        Remove every chunk whose `doc_id` matches.
        This triggers a full rebuild of index+graph+clusters inside Legra.
        """

        try:
            self.rag.delete_document(doc_id)
            _logger.info(f"LegraProvider: deleted {doc_id}")
            return True

        except Exception as e:
            _logger.exception(f"LegraProvider: delete_document failed for {doc_id}: {e}")
            return False

    async def get_document_ids(self, kb_id: str) -> Optional[List[str]]:
        """
        Return every `doc_id` that belongs to a given knowledge-base id.
        """

        ids = [
            m["doc_id"]
            for m in self.rag.docs_meta
            if m.get("kb_id") == kb_id
        ]
        return list(dict.fromkeys(ids))              # unique order-preserving


    async def search(
            self, query: str, limit: int = 5, kb_ids: List[str] | None = None
            ) -> List[Dict[str, Any]]:
        """
        Return the top-`limit` chunks.
        """
        results = []
        for kb_id in kb_ids:
            self.rag = Legra.load(kb_id)

            chunk_hits = self.rag.retriever.retrieve(query, limit)

            # Convert generator to list and extend the results
            results.extend([
                {
                    "id": f"{h['doc_id']}_chunk_{h['chunk_ix']}",
                    "content": h["text"],
                    "metadata": {k: v for k, v in h.items() if k not in ["text", "dist"]},
                    "score": 1.0 - min(h["distance"] / 2.0, 1.0),
                    }
                for h in chunk_hits
                ])

        return results

    async def finalize(self, kb_id: UUID):
        self.rag = Legra.load(str(kb_id))
        self.rag.complete_index_graph(str(kb_id))

