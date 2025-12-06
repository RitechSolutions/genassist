from abc import ABC, abstractmethod
from typing import Any, Dict, List

__all__ = [
    'Retriever',
]


class Retriever(ABC):
    """
    Abstract interface for retrieving top-k document chunks given a query.
    """

    @abstractmethod
    def retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """
        Given a text query, return a list of top_k results.

        Each result is a dictionary containing at least:
            - 'doc_id': str
            - 'chunk_ix': int
            - 'text': str
            - 'embedding': np.ndarray (optional)
            - 'distance': float (similarity/distance score)

        Returns:
            List of length top_k.
        """
        raise NotImplementedError
