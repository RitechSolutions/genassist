from pathlib import Path
from typing import Any, Dict, List

import faiss
import igraph as ig
import leidenalg as la
import numpy as np
import numpy.typing as npt
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from tqdm.auto import tqdm

from .chunking.semantic import Chunker
from .loaders import load_folder


class Legra:
    """
    A legal graph-rag based system.
    """

    def __init__(
        self,
        doc_path: str | Path,
        chunker: Chunker,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        custom_model: Any = None,
        extension: str = "txt",
        n_neighbors: int = 10,
        metric: str = "cosine",
        resolution: float = 1.0,
    ):
        self.doc_path = doc_path
        self.model = SentenceTransformer(model_name)
        self.extension = extension
        self.chunker = chunker
        self.custom_model = custom_model
        self.n_neighbors = n_neighbors
        self.metric = metric
        self.resolution = resolution

    def index(self):
        """Indexes the knowledge graph"""
        docs = load_folder(self.doc_path, self.extension)
        docs_chunked = {k: self.chunker(v) for k, v in tqdm(docs, desc="Chunking documents")}
        docs_embedded = {
            k: self.model.encode(chunks, convert_to_numpy=True)
            for k, chunks in tqdm(docs_chunked.items())
        }
        self.docs_meta: List[Dict[str, Any]] = []
        for doc_id, chunks in docs_chunked.items():
            embs = docs_embedded[doc_id]
            for idx, (chunk, emb) in enumerate(zip(chunks, embs)):
                self.docs_meta.append({
                    "doc_id": doc_id,
                    "chunk_ix": idx,
                    "text": chunk,
                    "embedding": emb,
                })

        dim = self.docs_meta[0]["embedding"].shape[0]
        self.index = faiss.IndexFlatIP(dim)
        emb_matrix = np.vstack([item["embedding"] for item in self.docs_meta])
        self.index.add(emb_matrix)
        self._knn_graph(emb_matrix, self.docs_meta)

    def _knn_graph(self, emb_matrix: npt.NDArray, docs_meta: List):
        """
        Constructs the kNN graph.
        """
        self.nbrs = NearestNeighbors(
            n_neighbors=self.n_neighbors,
            metric=self.metric,
        )
        self.nbrs.fit(emb_matrix)
        distances, indices = self.nbrs.kneighbors(emb_matrix)
        edges = []
        for i, neighbors in enumerate(indices):
            for j in neighbors:
                if i < j:  # undirected edges
                    edges.append((i, j))

        vertex_names = [f"{meta['doc_id']}_{meta['chunk_ix']}" for meta in docs_meta]
        graph = ig.Graph(
            n=len(docs_meta),
            vertex_attrs={"name": vertex_names},
            edges=edges,
            directed=False
        )
        partition = la.find_partition(
            graph,
            la.RBConfigurationVertexPartition,
            resolution_parameter=self.resolution,
        )
        # Attach community labels to metadata
        self.community_labels = partition.membership
        for idx, item in enumerate(docs_meta):
            item["community"] = self.community_labels[idx]

        self.graph = graph

    def query(self, query: str, top_k: int = 5) -> str:
        """Generate an answer to this query."""
        # Encode and normalize query
        q_emb = self.model.encode([query], convert_to_numpy=True)
        q_emb = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
        # Retrieve top-k chunks
        dists, inds = self.index.search(q_emb, top_k)
        retrieved = [self.docs_meta[i]["text"] for i in inds[0]]
        # Build context string
        context = "\n".join(retrieved)
        if self.custom_model:
            # Use provided custom generative model
            return self.custom_model.generate(context=context, query=query)
        # Fallback: return raw retrieved chunks
        return context
