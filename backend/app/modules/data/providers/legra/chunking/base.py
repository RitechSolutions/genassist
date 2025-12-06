from abc import ABC, abstractmethod
from typing import List, overload

__all__ = [
    'Chunker',
]


class Chunker(ABC):
    """
    Abstract base class for text chunking strategies.
    """
    @abstractmethod
    def _chunk_single(self, text: str) -> List[str]:
        raise NotImplementedError

    @overload
    def __call__(self, docs: str) -> List[str]:
        ...

    @overload
    def __call__(self, docs: List[str]) -> List[List[str]]:
        ...

    def __call__(self, docs: str | List[str]) -> List[str] | List[List[str]]:
        """
        Split a single document or a list of documents into chunks.

        Args:
            docs: Either a single string or a list of strings (documents).

        Returns:
            - If input is a single string: return List[str] (chunks).
            - If input is List[str]: return List[List[str]], where each element
              is chunks of that document.
        """
        if isinstance(docs, str):
            return self._chunk_single(docs)
        return [self._chunk_single(doc) for doc in docs]
