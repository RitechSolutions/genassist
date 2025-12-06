"""
Base Provider Interface

Defines the common interface that all data providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from .models import SearchResult

class BaseDataProvider(ABC):
    """
    Abstract base class for all data providers

    This interface ensures consistency across different provider implementations
    (vector, LEGRA, etc.) and enables polymorphic usage.
    """
    name: str
    
    def __init__(self, knowledge_base_id: str):
        """
        Initialize the provider with a knowledge base ID

        Args:
            knowledge_base_id: Unique identifier for the knowledge base
        """
        self.knowledge_base_id = knowledge_base_id
        self._initialized = False

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the provider

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Add a document to the provider

        Args:
            doc_id: Unique document identifier
            content: Document content
            metadata: Optional document metadata

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the provider

        Args:
            doc_id: Document identifier to delete

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_document_ids(self) -> List[str]:
        """
        Get all document IDs managed by this provider

        Returns:
            List of document identifiers
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 5,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search for documents using the provider's search mechanism

        Args:
            query: Search query
            limit: Maximum number of results to return
            **kwargs: Provider-specific search parameters

        Returns:
            List of search results
        """
        pass

    def is_initialized(self) -> bool:
        """
        Check if the provider is initialized

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get provider statistics and metadata

        Returns:
            Dictionary containing provider statistics
        """
        pass

    def close(self):
        """
        Clean up resources (optional override)

        Default implementation does nothing.
        Providers should override if they need cleanup.
        """
        pass


class FinalizableProvider(BaseDataProvider):
    """
    Extended interface for providers that support finalization

    Some providers (like LEGRA) require a finalization step after
    adding all documents to optimize their index.
    """

    @abstractmethod
    async def finalize(self) -> bool:
        """
        Finalize the provider after adding documents

        Returns:
            True if finalization successful, False otherwise
        """
        pass

    def requires_finalization(self) -> bool:
        """
        Check if this provider requires finalization

        Returns:
            True if finalization is required
        """
        return True
