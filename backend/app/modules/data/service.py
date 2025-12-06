"""
Data Source Service - Main orchestrator for vector and LEGRA providers
"""

import logging
from typing import Any, Dict, List, Optional

from .config import AgentRAGConfig, KbRAGConfig
from .providers import SearchResult, BaseDataProvider, LegraProvider, VectorProvider, LightRAGProvider, PlainProvider


logger = logging.getLogger(__name__)


class AgentRAGService:
    """
    Main service that orchestrates vector and LEGRA providers for a knowledge base
    """

    def __init__(self, config: AgentRAGConfig):
        self.config = config
        self.knowledge_base_id = config.knowledge_base_id
        self.data_provider: List[BaseDataProvider] = []
        self._initialized = False

    @staticmethod
    def from_kb_config(knowledge_base_id: str, config: Dict[str, Any]) -> 'AgentRAGService':

        if config is None or config.get("enabled", False) is False:
            config = AgentRAGConfig(knowledge_base_id=knowledge_base_id)
            return AgentRAGService(config)

        rag_config = KbRAGConfig(**config)

        vector = rag_config.get_vector_config()
        legra = rag_config.get_legra_config()
        lightrag = rag_config.get_lightrag_config()

        config = AgentRAGConfig(
            knowledge_base_id=knowledge_base_id,
            vector_config=vector,
            legra_config=legra,
            lightrag_config=lightrag,
        )
        return AgentRAGService(config)

    async def initialize(self) -> bool:
        """Initialize all enabled providers"""
        try:
            success = True

            # Initialize vector provider if enabled
            vector_config = self.config.get_vector_config()
            if vector_config:
                logger.info(
                    f"Initializing vector provider for KB {self.knowledge_base_id}")
                vector_provider = VectorProvider(
                    vector_config, self.knowledge_base_id)
                await vector_provider.initialize()
                if not vector_provider.is_initialized():
                    logger.error("Failed to initialize vector provider")
                    success = False
                else:
                    logger.info("Vector provider initialized successfully")
                    self.data_provider.append(vector_provider)
            # Initialize LEGRA provider if enabled
            legra_config = self.config.get_legra_config()
            if legra_config and legra_config.enabled:
                logger.info(
                    f"Initializing LEGRA provider for KB {self.knowledge_base_id}")
                legra_provider = LegraProvider(
                    legra_config, self.knowledge_base_id)
                if not legra_provider.initialize():
                    logger.error("Failed to initialize LEGRA provider")
                    success = False
                else:
                    logger.info("LEGRA provider initialized successfully")
                    self.data_provider.append(legra_provider)
            # Initialize LightRAG provider if enabled
            lightrag_config = self.config.get_lightrag_config()
            if lightrag_config and lightrag_config.enabled:
                logger.info(
                    f"Initializing LightRAG provider for KB {self.knowledge_base_id}")
                lightrag_provider = LightRAGProvider(
                    lightrag_config, self.knowledge_base_id)
                if not await lightrag_provider.initialize():
                    logger.error("Failed to initialize LightRAG provider")
                    success = False
                else:
                    logger.info("LightRAG provider initialized successfully")
                    self.data_provider.append(lightrag_provider)

            if not self.data_provider:
                logger.info(
                    f"Initializing Plain provider for KB {self.knowledge_base_id}")
                plain_provider = PlainProvider(self.knowledge_base_id)
                if not await plain_provider.initialize():
                    logger.error("Failed to initialize Plain provider")
                    success = False
                else:
                    logger.info("Plain provider initialized successfully")
                    self.data_provider.append(plain_provider)

            self._initialized = success
            logger.info(
                f"DataSourceService initialized for KB {self.knowledge_base_id}: {success}")
            return success

        except Exception as e:
            logger.error(f"Failed to initialize DataSourceService: {e}")
            return False

    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
        legra_finalize: bool = True
    ) -> Dict[str, bool]:
        """
        Add a document to all enabled providers

        Args:
            doc_id: Document identifier
            content: Document content
            metadata: Document metadata
            legra_finalize: Whether to finalize LEGRA after adding (build index/graph)

        Returns:
            Dictionary with provider results
        """
        if not self._initialized:
            logger.error("DataSourceService not initialized")
            return {}

        results = {}
        for provider in self.data_provider:
            try:
                if provider.name == "legra":
                    metadata["finalize"] = legra_finalize
                success = await provider.add_document(doc_id, content, metadata)
                results[provider.name] = success
            except Exception as e:
                logger.error(
                    f"{provider.name} add_document failed: {e}")
                results[provider.name] = False

        logger.info(f"Added document {doc_id}: {results}")
        return results

    async def delete_document(self, doc_id: str) -> Dict[str, bool]:
        """Delete a document from all enabled providers"""
        if not self._initialized:
            logger.error("DataSourceService not initialized")
            return {}

        results = {}

        for provider in self.data_provider:
            try:
                success = await provider.delete_document(doc_id)
                results[provider.name] = success
            except Exception as e:
                logger.error(
                    f"{provider.name} delete_document failed: {e}")
                results[provider.name] = False

        logger.info(f"Deleted document {doc_id}: {results}")
        return results

    async def get_document_ids(self) -> List[str]:
        """Get all document IDs from all providers (deduplicated)"""
        if not self._initialized:
            logger.error("DataSourceService not initialized")
            return []

        all_ids = set()
        for provider in self.data_provider:
            try:
                ids = await provider.get_document_ids()
                all_ids.update(ids)
            except Exception as e:
                logger.error(
                    f"{provider.name} get_document_ids failed: {e}")

        return list(all_ids)

    async def search(
        self,
        query: str,
        limit: int = 5,
        doc_ids: Optional[List[str]] = None,
        provider_weights: Optional[Dict[str, float]] = None,
    ) -> List[SearchResult]:
        """
        Search across all enabled providers and merge results

        Args:
            query: Search query
            limit: Maximum number of results
            doc_ids: Optional list of document IDs to restrict search
            provider_weights: Optional weights for each provider's results

        Returns:
            Merged and sorted search results
        """
        if not self._initialized:
            logger.error("DataSourceService not initialized")
            return []

        all_results = []

        # Default weights
        if provider_weights is None:
            provider_weights = {"vector": 1.0, "legra": 1.0, "lightrag": 1.0}

        # Search vector provider if available
        for provider in self.data_provider:
            try:
                vector_results = await provider.search(query, limit, doc_ids)
                # Apply weight to scores
                weight = provider_weights.get(provider.name, 1.0)
                for result in vector_results:
                    result.score *= weight
                all_results.extend(vector_results)
            except Exception as e:
                logger.error(f"Vector provider search failed: {e}")

        # Merge results, avoiding duplicates and sorting by score
        merged_results = self._merge_search_results(all_results)

        # Return top results
        return merged_results[:limit]

    def _merge_search_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Merge search results, handling duplicates by keeping highest score"""
        result_map = {}

        for result in results:
            existing = result_map.get(result.id)
            if existing is None or result.score > existing.score:
                result_map[result.id] = result

        # Sort by score descending
        merged = list(result_map.values())
        merged.sort(key=lambda x: x.score, reverse=True)

        return merged

    async def finalize_legra(self) -> bool:
        """Finalize LEGRA provider (build index and graph)"""
        legra_provider: Optional[LegraProvider] = next(
            (provider for provider in self.data_provider if provider.name == "legra"), None)
        if not legra_provider:
            logger.error("LEGRA provider not available")
            return False

        try:
            success = await legra_provider.finalize()
            logger.info(f"LEGRA finalization: {success}")
            return success
        except Exception as e:
            logger.error(f"LEGRA finalization failed: {e}")
            return False

    def get_provider_stats(self) -> Dict[str, Any]:
        """Get statistics from all providers"""
        stats = {
            "service": {
                "knowledge_base_id": self.knowledge_base_id,
                "initialized": self._initialized,
                "providers": []
            }
        }

        for provider in self.data_provider:
            provider_stats = provider.get_stats()
            stats["service"]["providers"].append(provider.name)
            stats["vector"] = provider_stats

        return stats

    def is_initialized(self) -> bool:
        """Check if service is initialized"""
        return self._initialized

    def has_vector_provider(self) -> bool:
        """Check if vector provider is available"""
        return any(provider.name == "vector" for provider in self.data_provider)

    def has_legra_provider(self) -> bool:
        """Check if LEGRA provider is available"""
        return any(provider.name == "legra" for provider in self.data_provider)

    def has_lightrag_provider(self) -> bool:
        """Check if LightRAG provider is available"""
        return any(provider.name == "lightrag" for provider in self.data_provider)
