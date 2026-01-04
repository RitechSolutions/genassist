from abc import ABC, abstractmethod
from typing import Any

__all__ = [
    'Generator',
]


class Generator(ABC):
    """
    Abstract interface for text-generation backends.
    """

    @abstractmethod
    def generate(self, query: str, context: str | None, **kwargs: Any) -> str:
        """
        Given a context (concatenated retrieved chunks) and a user query, return
        a generated answer. Additional kwargs may include max_length,
        temperature, etc.
        """
        raise NotImplementedError
