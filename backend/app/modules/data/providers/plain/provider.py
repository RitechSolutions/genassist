"""
Plain Provider Implementation

Implements the BaseDataProvider interface for simple document storage
without chunking, embedding, or vector operations. Returns content as-is.
"""

import logging
from typing import List, Dict, Any, Union
from ..base import BaseDataProvider
from ..models import SearchResult


logger = logging.getLogger(__name__)


class PlainProvider(BaseDataProvider):
    """
    Simple document storage provider that returns content as-is
    without any processing, chunking, or embedding.
    """
    name = "plain"

    def __init__(
        self,
        knowledge_base_id: str
    ):
        super().__init__(knowledge_base_id)
        self.documents: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> bool:
        """Initialize the plain provider"""
        try:
            self._initialized = True
            logger.info("PlainProvider initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize PlainProvider: {e}")
            return False

    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Union[Dict[str, Any], None] = None
    ) -> bool:
        """
        Add a document to the plain store

        Args:
            doc_id: Document identifier
            content: Document content
            metadata: Optional metadata

        Returns:
            Success status
        """
        try:
            if not self._initialized:
                if not await self.initialize():
                    return False

            if not content.strip():
                logger.warning(f"Empty content for document {doc_id}")
                return False

            # Prepare metadata
            if metadata is None:
                metadata = {}
            metadata["kb_id"] = self.knowledge_base_id
            metadata["doc_id"] = doc_id

            # Store document as-is without any processing
            self.documents[doc_id] = {
                "content": content,
                "metadata": metadata
            }

            logger.info(f"Added document {doc_id} to plain store")
            return True

        except Exception as e:
            logger.error(f"Failed to add document {doc_id}: {e}")
            return False

    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the plain store

        Args:
            doc_id: Document identifier

        Returns:
            Success status
        """
        try:
            if not self._initialized:
                if not await self.initialize():
                    return False

            if doc_id in self.documents:
                del self.documents[doc_id]
                logger.info(f"Deleted document {doc_id} from plain store")
                return True
            else:
                logger.info(f"Document {doc_id} not found in plain store")
                return True

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    async def search(
        self,
        query: str,
        limit: int = 5,
        filter_dict: Union[Dict[str, Any], None] = None,
        **kwargs
    ) -> List[SearchResult]:
        """
        Search the plain store - returns all documents as-is

        Args:
            query: Search query (ignored for plain provider)
            limit: Maximum number of results
            filter_dict: Optional metadata filters

        Returns:
            List of search results with content as-is
        """
        try:
            if not self._initialized:
                if not await self.initialize():
                    return []

            # Filter documents by knowledge base if specified
            filtered_docs = {}
            for doc_id, doc_data in self.documents.items():
                if filter_dict and self.knowledge_base_id:
                    if doc_data["metadata"].get("kb_id") != self.knowledge_base_id:
                        continue
                filtered_docs[doc_id] = doc_data

            # Convert to SearchResult format - return content as-is
            results = []
            for doc_id, doc_data in list(filtered_docs.items())[:limit]:
                search_result = SearchResult(
                    id=doc_id,
                    content=doc_data["content"],  # Return content as-is
                    metadata=doc_data["metadata"],
                    score=1.0,  # Plain provider doesn't do scoring
                    source="plain",
                    chunk_count=1  # Plain provider stores whole documents
                )
                results.append(search_result)

            logger.info(f"Plain search returned {len(results)} documents")
            return results

        except Exception as e:
            logger.error(f"Failed to search plain store: {e}")
            return []

    async def get_document_ids(self, kb_id: Union[str, None] = None) -> List[str]:
        """
        Get all document IDs for the knowledge base

        Args:
            kb_id: Knowledge base ID (uses instance kb_id if not provided)

        Returns:
            List of document IDs
        """
        try:
            if not self._initialized:
                if not await self.initialize():
                    return []

            # Use provided kb_id or fall back to instance kb_id
            filter_kb_id = kb_id or self.knowledge_base_id
            if not filter_kb_id:
                logger.warning("No knowledge base ID provided")
                return []

            # Get all document IDs from plain store
            doc_ids = []
            for doc_id, doc_data in self.documents.items():
                if doc_data["metadata"].get("kb_id") == filter_kb_id:
                    doc_ids.append(doc_id)

            return doc_ids

        except Exception as e:
            logger.error(f"Failed to get document IDs: {e}")
            return []

    def close(self):
        """Close plain provider (no external connections to close)"""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the plain provider"""
        return {
            "provider_type": "plain",
            "knowledge_base_id": self.knowledge_base_id,
            "initialized": self._initialized,
            "document_count": len(self.documents)
        }
