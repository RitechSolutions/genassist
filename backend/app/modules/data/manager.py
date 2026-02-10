"""
AgentRAGService Manager - Tenant-aware singleton for efficient service management

This module provides a tenant-aware singleton manager that creates and caches AgentRAGService
instances per knowledge base, ensuring tenant isolation while avoiding repeated initialization
and connection overhead.
"""

import asyncio
import logging
import os
import tempfile
import urllib.request
import urllib.parse
from typing import Dict, Optional, List, Any

from app.schemas.agent_knowledge import KBRead
from app.modules.data.utils import FileTextExtractor
from app.core.config.settings import file_storage_settings

from .service import AgentRAGService
from .providers import SearchResult
from .utils.doc import bulk_delete_documents, format_search_results

logger = logging.getLogger(__name__)


def _url_to_suffix(url: str) -> str:
    """Return a file suffix from URL path (e.g. .html, .pdf) for temp file extraction."""
    path = urllib.parse.urlparse(url).path
    if "." in path:
        return path[path.rindex(".") :]
    return ""


class AgentRAGServiceManager:
    """
    Tenant-aware singleton manager for AgentRAGService instances.

    This manager:
    1. Creates and caches service instances per knowledge base
    2. Provides tenant isolation - each tenant gets their own cache
    3. Reuses connections to avoid overhead
    4. Provides simplified API for common operations
    5. Handles initialization and cleanup
    """

    def __init__(self):
        self._services: Dict[str, AgentRAGService] = {}
        self._initialization_locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        logger.info("AgentRAGServiceManager initialized")

    async def get_service(self, kb_obj: KBRead) -> Optional[AgentRAGService]:
        """
        Get or create an AgentRAGService for a knowledge base

        Args:
            kb_obj: Knowledge base object with rag_config
            kb_id: Optional KB ID override

        Returns:
            AgentRAGService instance or None if creation fails
        """
        kb_id = str(kb_obj.id)

        # Return existing service if available and initialized
        if kb_id in self._services:
            service = self._services[kb_id]
            if service.is_initialized():
                return service
            else:
                # Remove failed service
                logger.warning(
                    f"Removing uninitialized service for KB {kb_id}")
                await self._remove_service(kb_id)

        # Ensure we have a lock for this KB
        if kb_id not in self._initialization_locks:
            self._initialization_locks[kb_id] = asyncio.Lock()

        # Use lock to prevent concurrent initialization
        async with self._initialization_locks[kb_id]:
            # Double-check pattern - service might have been created while waiting
            if kb_id in self._services and self._services[kb_id].is_initialized():
                return self._services[kb_id]

            try:
                # Create service
                service = AgentRAGService.from_kb_config(
                    kb_id, kb_obj.rag_config)
                if not service:
                    logger.error(
                        f"Failed to create AgentRAGService for KB {kb_id}")
                    return None

                # Initialize service
                success = await service.initialize()
                if not success:
                    logger.error(
                        f"Failed to initialize AgentRAGService for KB {kb_id}")
                    return None

                # Cache the service
                self._services[kb_id] = service
                logger.info(
                    f"Created and cached AgentRAGService for KB {kb_id}")
                return service

            except Exception as e:
                logger.error(
                    f"Error creating AgentRAGService for KB {kb_id}: {e}")
                return None

    async def add_document(
        self,
        kb_obj: KBRead,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
        legra_finalize: bool = False,
    ) -> Dict[str, bool]:
        """
        Add a document to a knowledge base

        Args:
            kb_obj: Knowledge base object
            doc_id: Document identifier
            content: Document content
            metadata: Document metadata
            legra_finalize: Whether to finalize LEGRA

        Returns:
            Dictionary with provider results
        """
        service = await self.get_service(kb_obj)
        if not service:
            logger.error(f"Could not get service for KB {kb_obj.id}")
            return {}

        return await service.add_document(doc_id, content, metadata, legra_finalize)

    async def delete_document(self, kb_obj: KBRead, doc_id: str) -> Dict[str, bool]:
        """
        Delete a document from a knowledge base

        Args:
            kb_obj: Knowledge base object
            doc_id: Document identifier

        Returns:
            Dictionary with provider results
        """
        service = await self.get_service(kb_obj)
        if not service:
            logger.error(f"Could not get service for KB {kb_obj.id}")
            return {}

        return await service.delete_document(doc_id)

    async def search(
        self,
        kb_objects: List[KBRead],
        query: str,
        limit: int = 5,
        format_results: bool = False,
        force_limit: bool = False,
    ) -> List[SearchResult] | str:
        """
        Search across multiple knowledge bases

        Args:
            kb_objects: List of knowledge base objects
            query: Search query
            limit: Maximum results
            format_results: Whether to format as string

        Returns:
            Search results or formatted string
        """
        all_results = []

        for kb_obj in kb_objects:
            service = await self.get_service(kb_obj)
            if service:
                try:
                    results = await service.search(query, limit)
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"Search failed for KB {kb_obj.id}: {e}")

        # Sort by score and limit
        all_results.sort(key=lambda x: x.score, reverse=True)
        final_results = all_results[:limit]

        if format_results:
            return format_search_results(final_results, include_metadata=False)

        return final_results

    async def get_document_ids(self, kb_obj: KBRead) -> List[str]:
        """
        Get document IDs for a knowledge base

        Args:
            kb_obj: Knowledge base object

        Returns:
            List of document IDs
        """
        service = await self.get_service(kb_obj)
        if not service:
            return []

        return await service.get_document_ids()

    async def finalize_legra(self, kb_obj: KBRead) -> bool:
        """
        Finalize LEGRA for a knowledge base

        Args:
            kb_obj: Knowledge base object

        Returns:
            Success status
        """
        service = await self.get_service(kb_obj)
        if not service:
            return False

        if service.has_legra_provider():
            return await service.finalize_legra()
        else:
            logger.warning(f"No LEGRA provider for KB {kb_obj.id}")
            return False

    async def load_knowledge_items(
        self, knowledge_items: List[KBRead], action: str
    ) -> List[Dict[str, Any]]:
        """
        Load multiple knowledge items efficiently

        Args:
            knowledge_items: List of knowledge base items

        Returns:
            List of processing results
        """
        results = []

        # Initialize the file text extractor
        extractor = FileTextExtractor()

        # Group by KB for efficient processing
        kb_groups = {}
        for item in knowledge_items:
            kb_id = str(item.id)
            if kb_id not in kb_groups:
                kb_groups[kb_id] = []
            kb_groups[kb_id].append(item)

        for kb_id, items in kb_groups.items():
            if not items:
                continue

            # Use first item to get service
            representative_item = items[0]
            service = await self.get_service(representative_item)

            if not service:
                logger.warning(f"Could not get service for KB {kb_id}")
                continue

            if action == "update":
                # Get all existing document IDs from RAG storage and delete them
                existing_ids = await service.get_document_ids()
                if existing_ids:
                    delete_result: dict = await bulk_delete_documents(service, existing_ids)
                    logger.debug(
                        f"KB document deletion results: {delete_result}")

            # Process all items for this KB
            for item in items:
                try:
                    doc_ids = [f"KB:{kb_id}#content"]
                    contents = [getattr(item, "content", "")]

                    # Handle file content
                    if (
                        getattr(item, "type", "") == "file"
                        and hasattr(item, "files")
                        and item.files
                    ):

                        doc_ids = []
                        contents = []

                        for idx, file_item in enumerate(item.files):
                            try:
                                # Handle URL string (files stored as list of URLs), path string, or legacy dict
                                if isinstance(file_item, str):
                                    doc_ids.append(f"KB:{kb_id}#file_{idx}:{file_item}")
                                    if file_item.startswith("http://") or file_item.startswith("https://"):
                                        temp_content = self._download_url_to_temp_file(file_item, extractor)
                                        # Download from URL to temp file and extract
                                        contents.append(content)
                                    else:
                                        # Local file path
                                        contents.append(extractor.extract(path=file_item))
                                elif isinstance(file_item, dict):
                                    # Legacy format: dict with file_path and/or url/urls
                                    file_path = file_item.get("file_path")
                                    file_url = file_item.get("url") or file_item.get("urls")
                                    file_storage_provider = file_storage_settings.FILE_MANAGER_PROVIDER or "local"

                                    # Handle url from file manager and other providers vs local file path
                                    if file_storage_provider != "local" and file_url and (file_url.startswith("http://") or file_url.startswith("https://")):
                                        doc_ids.append(f"KB:{kb_id}#file_{idx}:{file_url}")
                                        temp_content = self._download_url_to_temp_file(file_url, extractor)
                                        contents.append(temp_content)
                                    elif file_storage_provider == "local" and file_path:
                                        doc_ids.append(f"KB:{kb_id}#file_{idx}:{file_path}")
                                        contents.append(extractor.extract(path=file_path))
                                    else:
                                        logger.warning(f"File item {idx} missing file_path or url: {file_item}")

                            except Exception as e:
                                file_path_str = (
                                    file_item
                                    if isinstance(file_item, str)
                                    else file_item.get("file_path") or file_item.get("url") or file_item.get("urls") or "unknown"
                                )
                                logger.error(
                                    f"Error extracting file {file_path_str}: {e}")

                    # Handle URL content
                    elif getattr(item, "type", "") == "url":
                        from app.core.utils.bi_utils import set_url_content_if_has_rag

                        await set_url_content_if_has_rag(item)
                        contents = [getattr(item, "content", "")]

                    for doc_id, content in zip(doc_ids, contents):

                        metadata = {
                            "name": getattr(item, "name", ""),
                            "description": getattr(item, "description", ""),
                            "id": doc_id,
                            "kb_id": kb_id,
                        }

                        result = await service.add_document(
                            doc_id,
                            content,
                            metadata,
                            legra_finalize=getattr(
                                item, "legra_finalize", False),
                        )
                        results.append({"id": doc_id, "result": result})

                except Exception as e:
                    logger.error(f"Error loading item {item.id}: {e}")
                    results.append(
                        {"id": doc_id, "result": {}, "error": str(e)})

        return results

    async def _remove_service(self, kb_id: str):
        """Remove a service from cache"""
        if kb_id in self._services:
            del self._services[kb_id]
        if kb_id in self._initialization_locks:
            del self._initialization_locks[kb_id]

    async def cleanup_service(self, kb_id: str):
        """
        Clean up a specific service (useful when KB is deleted)

        Args:
            kb_id: Knowledge base ID
        """
        async with self._lock:
            await self._remove_service(str(kb_id))
            logger.info(f"Cleaned up service for KB {kb_id}")

    async def cleanup_all(self):
        """Clean up all services"""
        async with self._lock:
            self._services.clear()
            self._initialization_locks.clear()
            logger.info("Cleaned up all AgentRAGService instances")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about cached services"""
        return {
            "total_services": len(self._services),
            "initialized_services": sum(
                1 for s in self._services.values() if s.is_initialized()
            ),
            "service_ids": list(self._services.keys()),
        }

    def _download_url_to_temp_file(self, url: str, extractor: FileTextExtractor) -> str:
        """Create a temporary file from a URL"""

        # Download from URL to temp file and extract
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=_url_to_suffix(url),
        ) as tmp:
            urllib.request.urlretrieve(url, tmp.name)
        try:
            return extractor.extract(path=tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
        return ""