"""
Utility functions for the data module
"""

import logging
from typing import Any, Dict, List, Optional

from ..providers.models import SearchResult
from ..service import AgentRAGService

logger = logging.getLogger(__name__)


async def bulk_add_documents(
    service: AgentRAGService,
    documents: List[Dict[str, Any]],
    batch_size: int = 10,
    legra_finalize_at_end: bool = True
) -> Dict[str, Any]:
    """
    Add multiple documents to a AgentRAGService in batches

    Args:
        service: The AgentRAGService instance
        documents: List of documents with keys: doc_id, content, metadata
        batch_size: Number of documents to process concurrently
        legra_finalize_at_end: Whether to finalize LEGRA after all documents are added

    Returns:
        Summary of operations
    """
    if not service.is_initialized():
        logger.error("Service not initialized")
        return {"error": "Service not initialized"}

    total = len(documents)
    processed = 0
    successful = 0
    failed = 0
    errors = []

    # Process in batches
    for i in range(0, total, batch_size):
        batch = documents[i:i + batch_size]

        # Create tasks for concurrent processing
        tasks = []
        for doc in batch:
            doc_id = doc.get("doc_id", f"doc_{i}")
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            # Don't finalize LEGRA for individual documents
            task = service.add_document(
                doc_id, content, metadata, legra_finalize=False)
            tasks.append((doc_id, task))

        # Execute batch
        for doc_id, task in tasks:
            try:
                result = await task
                processed += 1
                if any(result.values()):  # At least one provider succeeded
                    successful += 1
                else:
                    failed += 1
                    errors.append(f"Failed to add document {doc_id}")
            except Exception as e:
                processed += 1
                failed += 1
                errors.append(f"Error adding document {doc_id}: {str(e)}")

        logger.info(
            f"Processed batch {i//batch_size + 1}: {processed}/{total} documents")

    # Finalize LEGRA if requested and available
    legra_finalized = False
    if legra_finalize_at_end and service.has_legra_provider():
        try:
            legra_finalized = await service.finalize_legra()
            logger.info(f"LEGRA finalization: {legra_finalized}")
        except Exception as e:
            logger.error(f"LEGRA finalization failed: {e}")
            errors.append(f"LEGRA finalization failed: {str(e)}")

    return {
        "total": total,
        "processed": processed,
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "legra_finalized": legra_finalized
    }


async def bulk_delete_documents(
    service: AgentRAGService,
    doc_ids: List[str],
    batch_size: int = 10
) -> Dict[str, Any]:
    """
    Delete multiple documents from a AgentRAGService in batches

    Args:
        service: The AgentRAGService instance
        doc_ids: List of document IDs to delete
        batch_size: Number of documents to process concurrently

    Returns:
        Summary of operations
    """
    if not service.is_initialized():
        logger.error("Service not initialized")
        return {"error": "Service not initialized"}

    total = len(doc_ids)
    processed = 0
    successful = 0
    failed = 0
    errors = []

    # Process in batches
    for i in range(0, total, batch_size):
        batch = doc_ids[i:i + batch_size]

        # Create tasks for concurrent processing
        tasks = []
        for doc_id in batch:
            task = service.delete_document(doc_id)
            tasks.append((doc_id, task))

        # Execute batch
        for doc_id, task in tasks:
            try:
                result = await task
                processed += 1
                if any(result.values()):  # At least one provider succeeded
                    successful += 1
                else:
                    failed += 1
                    errors.append(f"Failed to delete document {doc_id}")
            except Exception as e:
                processed += 1
                failed += 1
                errors.append(f"Error deleting document {doc_id}: {str(e)}")

        logger.info(
            f"Processed batch {i//batch_size + 1}: {processed}/{total} documents")

    return {
        "total": total,
        "processed": processed,
        "successful": successful,
        "failed": failed,
        "errors": errors
    }


def format_search_results(
    results: List[SearchResult],
    include_metadata: bool = True,
    max_content_length: Optional[int] = None
) -> str:
    """
    Format search results for display or LLM consumption

    Args:
        results: List of search results
        include_metadata: Whether to include metadata in output
        max_content_length: Maximum length of content to include

    Returns:
        Formatted string representation
    """
    if not results:
        return "No results found."

    formatted_parts = []
    formatted_parts.append(f"Found {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        content = result.content
        if max_content_length and len(content) > max_content_length:
            content = content[:max_content_length] + "..."

        part = f"--- Result {i} (Score: {result.score:.3f}, Source: {result.source}) ---\n"
        part += f"ID: {result.id}\n"
        part += f"Content: {content}\n"

        if include_metadata and result.metadata:
            part += f"Metadata: {result.metadata}\n"

        formatted_parts.append(part)

    return "\n".join(formatted_parts)


async def migrate_documents_between_providers(
    source_service: AgentRAGService,
    target_service: AgentRAGService,
    doc_ids: Optional[List[str]] = None,
    batch_size: int = 10
) -> Dict[str, Any]:
    """
    Migrate documents from one service to another

    Args:
        source_service: Source AgentRAGService
        target_service: Target AgentRAGService
        doc_ids: Optional list of specific document IDs to migrate
        batch_size: Batch size for processing

    Returns:
        Migration summary
    """
    if not source_service.is_initialized() or not target_service.is_initialized():
        return {"error": "Both services must be initialized"}

    # Get document IDs to migrate
    if doc_ids is None:
        doc_ids = await source_service.get_document_ids()

    # For migration, we would need to extract the original content
    # This is a simplified implementation - in practice, you might need
    # to store original content separately or extract it from search results

    logger.warning(
        "Document migration requires original content storage - not fully implemented")

    return {
        "total": len(doc_ids),
        "note": "Migration requires original document content to be available"
    }


async def health_check(service: AgentRAGService) -> Dict[str, Any]:
    """
    Perform a health check on a AgentRAGService

    Args:
        service: The service to check

    Returns:
        Health check results
    """
    health = {
        "service_initialized": service.is_initialized(),
        "providers": {},
        "overall_status": "unknown"
    }

    if not service.is_initialized():
        health["overall_status"] = "unhealthy"
        health["error"] = "Service not initialized"
        return health

    # Check vector provider
    if service.has_vector_provider():
        health["providers"]["vector"] = {
            "available": True,
            "initialized": service.vector_provider.is_initialized()
        }
    else:
        health["providers"]["vector"] = {"available": False}

    # Check LEGRA provider
    if service.has_legra_provider():
        health["providers"]["legra"] = {
            "available": True,
            "initialized": service.legra_provider.is_initialized()
        }
    else:
        health["providers"]["legra"] = {"available": False}

    # Determine overall status
    available_providers = [
        p for p in health["providers"].values() if p["available"]]
    initialized_providers = [
        p for p in available_providers if p.get("initialized", False)]

    if len(initialized_providers) == len(available_providers) and len(available_providers) > 0:
        health["overall_status"] = "healthy"
    elif len(initialized_providers) > 0:
        health["overall_status"] = "degraded"
    else:
        health["overall_status"] = "unhealthy"

    # Get provider stats
    try:
        health["stats"] = service.get_provider_stats()
    except Exception as e:
        health["stats_error"] = str(e)

    return health
