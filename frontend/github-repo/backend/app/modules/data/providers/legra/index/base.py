from abc import ABC, abstractmethod
from typing import Tuple

import numpy.typing as npt

__all__ = [
    'Indexer',
]


class Indexer(ABC):
    """
    Abstract interface for vector indexers (for building and searching).
    """

    @abstractmethod
    def build_index(self, embeddings: npt.NDArray) -> None:
        """
        Build internal index given a 2D array of embeddings.

        Args:
            embeddings: numpy array of shape (N, D).
        """
        raise NotImplementedError

    @abstractmethod
    def search(self, queries: npt.NDArray, top_k: int) -> Tuple[npt.NDArray, npt.NDArray]:
        """
        Run a search on the built index with given query vectors.

        Args:
            queries: numpy array of shape (M, D). top_k: number of neighbors to
            retrieve per query.

        Returns:
            - distances: np.ndarray of shape (M, top_k)
            - indices:   np.ndarray of shape (M, top_k)
        """
        raise NotImplementedError
