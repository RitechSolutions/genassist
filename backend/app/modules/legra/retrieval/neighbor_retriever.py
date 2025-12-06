from typing import Any, Dict, List

from ..embedding import Embedder
from ..index import Indexer
from ..retrieval import Retriever

__all__ = [
    'NeighborRetriever',
]


class NeighborRetriever(Retriever):
    """
    Retrieve top_k chunks by embedding the query, then searching the indexer.
    Requires:
      - an Embedder to turn query -> embedding
      - an Indexer that has been built on all chunk embeddings
      - docs_meta: a list of metadata dicts, one per indexed chunk
    """

    def __init__(
        self,
        embedder: Embedder,
        indexer: Indexer,
        docs_meta: List[Dict[str, Any]],
    ) -> None:
        self.embedder = embedder
        self.indexer = indexer
        # List of dicts with keys 'doc_id','chunk_ix','text','embedding', etc.
        self.docs_meta = docs_meta

    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        # 1) Embed the query
        q_emb = self.embedder.encode([query])  # shape (1, D)
        # 2) Search index
        distances, indices = self.indexer.search(q_emb, top_k)  # shapes (1, k), (1, k)
        distances = distances[0]
        indices = indices[0]
        results: List[Dict[str, Any]] = []

        for dist, idx in zip(distances, indices):
            meta = self.docs_meta[idx].copy()
            meta["distance"] = float(dist)
            results.append(meta)

        return results
