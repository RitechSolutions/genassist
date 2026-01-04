from typing import Tuple

import faiss
import numpy as np
import numpy.typing as npt

from .base import Indexer

__all__ = [
    'FaissFlatIndexer',
]


class FaissFlatIndexer(Indexer):
    """
    Exact inner-product indexer using faiss.IndexFlatIP or L2-based, etc.
    """

    def __init__(self, dim: int, use_gpu: bool = False):
        self.dim = dim
        self.use_gpu = use_gpu
        # We'll store the index in self.index
        self.index: faiss.Index | None = None

    def build_index(self, embeddings: npt.NDArray) -> None:
        """
        Build a FAISS flat (exact) index. We normalize embeddings first.
        """
        # Normalize for inner‐product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12
        embs_normed = embeddings / norms
        index = faiss.IndexFlatIP(self.dim)

        if self.use_gpu and faiss.get_num_gpus() > 0:
            res = faiss.StandardGpuResources()
            index = faiss.index_cpu_to_gpu(res, 0, index)

        index.add(embs_normed)
        self.index = index

    def search(self, queries: npt.NDArray, top_k: int) -> Tuple[npt.NDArray, npt.NDArray]:
        """
        Search the built FAISS index using normalized queries.
        """
        if self.index is None:
            raise ValueError("Faiss index has not been built.")

        # Normalize queries
        norms = np.linalg.norm(queries, axis=1, keepdims=True) + 1e-12
        q_normed = queries / norms

        # FAISS expects float32
        dists, idxs = self.index.search(q_normed.astype(np.float32), top_k)
        return dists, idxs
