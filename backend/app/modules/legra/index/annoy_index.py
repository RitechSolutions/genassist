from typing import Tuple

import numpy as np
import numpy.typing as npt
from annoy import AnnoyIndex

from .base import Indexer

__all__ = [
    'AnnoyIndexer',
]


class AnnoyIndexer(Indexer):
    """
    Approximate nearest neighbor index using Annoy (angular distance).
    """

    def __init__(self, dim: int, n_trees: int = 10, metric: str = "angular"):
        self.dim = dim
        self.n_trees = n_trees
        self.metric = metric
        self.index: AnnoyIndex | None = None

    def build_index(self, embeddings: npt.NDArray) -> None:
        """
        Build Annoy index. We'll assume embeddings are normalized if using 'angular'.
        """
        self.index = AnnoyIndex(self.dim, self.metric)
        for i, vec in enumerate(embeddings.astype(np.float32)):
            self.index.add_item(i, vec.tolist())
        self.index.build(self.n_trees)

    def search(self, queries: npt.NDArray, top_k: int) -> Tuple[npt.NDArray, npt.NDArray]:
        """
        Query the Annoy index. Annoy only returns indices; distances need to be computed manually.
        """
        if self.index is None:
            raise ValueError("Annoy index has not been built.")

        # Prepare outputs
        M = queries.shape[0]
        dists = np.zeros((M, top_k), dtype=np.float32)
        idxs = np.zeros((M, top_k), dtype=np.int64)

        for i, q_vec in enumerate(queries.astype(np.float32)):
            neighbors, distances = self.index.get_nns_by_vector(
                q_vec.tolist(), top_k, include_distances=True
            )
            idxs[i, :] = np.array(neighbors, dtype=np.int64)
            dists[i, :] = np.array(distances, dtype=np.float32)

        return dists, idxs
