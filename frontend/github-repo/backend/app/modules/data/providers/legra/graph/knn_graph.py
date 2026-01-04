from typing import List, Tuple

import igraph as ig
import numpy.typing as npt
from sklearn.neighbors import NearestNeighbors

__all__ = [
    'KNNGraphBuilder',
]


class KNNGraphBuilder:
    """
    Build an undirected kNN graph from an embedding matrix.

    - Each node corresponds to one embedding vector.
    - Edges connect nodes if they are among each other's top-k nearest
      neighbors.
    """

    def __init__(self, n_neighbors: int = 10, metric: str = "cosine"):
        self.n_neighbors = n_neighbors
        self.metric = metric
        # We optionally keep a fitted sklearn NearestNeighbors for
        # reproducibility
        self._nbrs: NearestNeighbors = NearestNeighbors(
            n_neighbors=self.n_neighbors,
            metric=self.metric,
        )


    def fit(self, emb_matrix: npt.NDArray) -> Tuple[ig.Graph, List[Tuple[int, int]]]:
        """
        Build the k-NN graph from emb_matrix (N × D).
        """
        N = emb_matrix.shape[0]
        if N < 2:  # nothing to connect
            return ig.Graph(n=N), []

        # Fit the index once
        self._nbrs.fit(emb_matrix)

        # Choose a legal number of neighbours
        k_builtin = getattr(self._nbrs, "n_neighbors", 10)
        k = min(k_builtin, N - 1)  # ▸ ensures k ≤ N - 1

        # Query neighbours
        distances, indices = self._nbrs.kneighbors(emb_matrix, n_neighbors=k)

        # Build undirected edge list
        edges: List[Tuple[int, int]] = []
        for i, nbrs in enumerate(indices):
            for j in nbrs:
                if i < j:
                    edges.append((i, j))

        graph = ig.Graph(n=N, edges=edges, directed=False)
        return graph, edges

