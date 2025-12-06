from abc import ABC, abstractmethod
from typing import List

import numpy.typing as npt

__all__ = [
    'Embedder',
]


class Embedder(ABC):
    """
    Abstract interface for document/chunk embedding.
    """
    model_name: str = ""

    @abstractmethod
    def encode(self, texts: List[str]) -> npt.NDArray:
        """
        Convert a batch of texts into embeddings.

        Args:
            texts: List of strings to embed.

        Returns:
            A 2D numpy array of shape (len(texts), embedding_dim).
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        Return the dimensionality of embeddings produced by this embedder.
        """
        raise NotImplementedError
