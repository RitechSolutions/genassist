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
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from app.core.config.settings import file_storage_settings
from app.db.models import StorageProvider
from app.modules.data.utils import FileTextExtractor
from app.schemas.agent_knowledge import KBBase, KBRead

from .providers import SearchResult
from .service import AgentRAGService
from .utils.doc import bulk_delete_documents, format_search_results

logger = logging.getLogger(__name__)

ARTICLE_SYNC_KB_TYPES = ("zendesk", "salesforce")
FILE_SYNC_KB_TYPES = ("s3", "sharepoint", "smb_share_folder", "azure_blob", "google_bucket")
SYNC_OWNED_KB_TYPES = ARTICLE_SYNC_KB_TYPES + FILE_SYNC_KB_TYPES


EMBEDDING_STORAGE_FIELDS = ("type", "model_name", "model_id", "max_length", "normalize_embeddings")
LEGRA_STORAGE_FIELDS = (
    "enabled", "embedding_model", "min_sents", "max_sents", "min_sent_length", "n_neighbors", "metric",
    "cluster_resolution", "working_dir",
)
LIGHTRAG_STORAGE_FIELDS = (
    "enabled", "working_dir", "embedding_func_name", "llm_model_func_name", "chunk_token_size",
    "chunk_overlap_token_size", "vector_storage", "vector_db_storage_cls_kwargs",
)


def _pick(section: Optional[Dict[str, Any]], fields: tuple) -> Optional[Dict[str, Any]]:
    return {field: section.get(field) for field in fields} if section else None


def _vector_storage_setup(vector: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Vector settings that decide what is stored and where; pgvector always uses the tenant database."""
    if not vector:
        return None
    database = vector["vector_db"]
    uses_own_server = database["type"] != "pgvector"
    database_fields = ("type", "collection_name") + (("host", "port", "persist_directory") if uses_own_server else ())
    return {
        "enabled": vector["enabled"],
        "chunking": vector["chunking"],
        "embedding": _pick(vector["embedding"], EMBEDDING_STORAGE_FIELDS),
        "vector_db": _pick(database, database_fields),
    }


def _stored_content_setup(rag_config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The settings a KB's stored documents depend on; settings only used when searching are left out."""
    setup = AgentRAGService.from_kb_config("", rag_config).config.model_dump()
    return {
        "vector": _vector_storage_setup(setup.get("vector_config")),
        "legra": _pick(setup.get("legra_config"), LEGRA_STORAGE_FIELDS),
        "lightrag": _pick(setup.get("lightrag_config"), LIGHTRAG_STORAGE_FIELDS),
    }


def _rag_config_changed(stored: Optional[Dict[str, Any]], incoming: Dict[str, Any]) -> bool:
    """True when the saved settings change what the KB stores; unreadable settings count as unchanged."""
    try:
        return _stored_content_setup(stored) != _stored_content_setup(incoming)
    except Exception:
        return False


def _first_url(urls: Optional[List[str]]) -> Optional[str]:
    return urls[0] if urls else None


def _file_sync_source_changed(current: KBRead, incoming: KBBase) -> bool:
    """True when a save points a file-synced KB at another data source or SharePoint site."""
    source_changed = incoming.sync_source_id is not None and current.sync_source_id != incoming.sync_source_id
    site_given = incoming.type == "sharepoint" and incoming.urls is not None
    site_changed = site_given and _first_url(current.urls) != _first_url(incoming.urls)
    return source_changed or site_changed


def save_load_action(current: KBRead, incoming: KBBase) -> str:
    """Return "clear" when a save makes a synced KB's documents outdated, otherwise "update"."""
    if incoming.type not in SYNC_OWNED_KB_TYPES:
        return "update"
    type_changed = current.type != incoming.type
    rag_config_changed = incoming.rag_config is not None and _rag_config_changed(current.rag_config, incoming.rag_config)
    file_sync_inputs_changed = incoming.type in FILE_SYNC_KB_TYPES and (
        rag_config_changed or _file_sync_source_changed(current, incoming)
    )
    return "clear" if type_changed or file_sync_inputs_changed else "update"


def _service_setup(kb_id: str, rag_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The full setup a KB's service is built from; None when the settings cannot be read."""
    try:
        return AgentRAGService.from_kb_config(kb_id, rag_config).config.model_dump()
    except Exception:
        return None


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
        self._service_setups: Dict[str, Optional[Dict[str, Any]]] = {}
        self._initialization_locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        logger.info("AgentRAGServiceManager initialized")

    def _cached_service_is_current(self, kb_id: str, requested_setup: Optional[Dict[str, Any]]) -> bool:
        """True when the cached service is ready and was built from the settings the KB has now."""
        service = self._services.get(kb_id)
        if not service or not service.is_initialized():
            return False
        settings_unreadable = requested_setup is None
        return settings_unreadable or self._service_setups.get(kb_id) == requested_setup

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
        # Each process keeps its own cache, so a settings change saved elsewhere is caught here.
        requested_setup = _service_setup(kb_id, kb_obj.rag_config)

        if self._cached_service_is_current(kb_id, requested_setup):
            return self._services[kb_id]
        if kb_id in self._services:
            logger.warning(f"Rebuilding service for KB {kb_id}: it is not initialized or its settings changed")
            await self._remove_service(kb_id)

        # Ensure we have a lock for this KB
        if kb_id not in self._initialization_locks:
            self._initialization_locks[kb_id] = asyncio.Lock()

        # Use lock to prevent concurrent initialization
        async with self._initialization_locks[kb_id]:
            # Double-check pattern - service might have been created while waiting
            if self._cached_service_is_current(kb_id, requested_setup):
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
                self._service_setups[kb_id] = requested_setup
                logger.info(
                    f"[AgentRAGServiceManager] Created and cached AgentRAGService for KB {kb_id}")
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

    async def clear_documents(self, kb_obj: KBRead) -> None:
        """Delete every document of a knowledge base from the stores its settings point to."""
        try:
            service = await self.get_service(kb_obj)
            if not service:
                logger.warning(f"Could not get service for KB {kb_obj.id}")
                return
            delete_result = await service.delete_by_metadata({"kb_id": str(kb_obj.id)})
            # Stores without a bulk delete (such as LEGRA) still list their documents.
            remaining_ids = await service.get_document_ids()
            if remaining_ids:
                await bulk_delete_documents(service, remaining_ids)
            logger.info(f"Cleared documents of KB {kb_obj.id}: {delete_result}, {len(remaining_ids)} removed one by one")
        except Exception as e:
            logger.error(f"Failed to clear documents of KB {kb_obj.id}: {e}")

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

            # Leave synced KBs untouched because their sync tasks own their documents.
            kb_type = getattr(representative_item, "type", "")
            if kb_type in SYNC_OWNED_KB_TYPES:
                logger.info(
                    f"Skipping generic RAG load for {kb_type} KB {kb_id}; "
                    "handled by its sync task"
                )
                continue

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
                                        temp_content = await self._download_url_to_temp_file(file_item, extractor, delete_file=True)
                                        # Download from URL to temp file and extract
                                        contents.append(temp_content)
                                    else:
                                        # Local file path
                                        contents.append(extractor.extract(path=file_item))
                                elif isinstance(file_item, dict):
                                    # Legacy format: dict with file_path and/or url/urls
                                    file_path = file_item.get("file_path")
                                    # file_url = file_item.get("url") or file_item.get("urls")
                                    file_url = file_item.get("file_url")
                                    # file storage provider
                                    file_storage_provider = file_item.get("storage_provider") or file_storage_settings.FILE_MANAGER_PROVIDER or StorageProvider.LOCAL

                                    # Handle url from file manager and other providers vs local file path
                                    if file_storage_provider == StorageProvider.S3 and file_url and (file_url.startswith("http://") or file_url.startswith("https://")):
                                        doc_ids.append(f"KB:{kb_id}#file_{idx}:{file_url}")
                                        temp_content = await self._download_url_to_temp_file(file_url, extractor, delete_file=True)
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
        self._service_setups.pop(kb_id, None)
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
            self._service_setups.clear()
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

    def _url_to_suffix(self, url: str) -> str:
        """Return a file suffix from URL path (e.g. .html, .pdf) for temp file extraction."""
        path = urllib.parse.urlparse(url).path
        if "." in path:
            return path[path.rindex(".") :]
        return ""

    async def _download_url_to_temp_file(
        self,
        url: str,
        extractor: FileTextExtractor,
        delete_file: bool = False
    ) -> str:
        """Download a URL to a temporary file, extract its content, and optionally delete it."""

        tmp_path: str | None = None
        try:
            # Always create a non-deleting temp file so downstream extractors
            # can safely reopen it on all platforms.
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=self._url_to_suffix(url),
            ) as tmp:
                urllib.request.urlretrieve(url, tmp.name)
                tmp_path = tmp.name

            return extractor.extract(path=tmp_path)
        finally:
            if delete_file and tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
