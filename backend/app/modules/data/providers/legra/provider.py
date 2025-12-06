"""
LEGRA Provider Implementation

Implements the BaseDataProvider interface for LEGRA-based graph search.
"""

import logging
from typing import List, Dict, Any, Optional
from .config import LegraConfig
from ..base import FinalizableProvider, SearchResult
from ..legra import FaissFlatIndexer, HuggingFaceGenerator, Legra, LeidenClusterer, SemanticChunker, \
    SentenceTransformerEmbedder
logger = logging.getLogger(__name__)


class LegraProvider(FinalizableProvider):
    """
    LEGRA provider for graph-based retrieval and generation

    This provider handles:
    - Graph-based document storage
    - Community detection and clustering
    - Graph-based retrieval with context
    - Generative responses from retrieved context
    """
    name = "legra"
    
    def __init__(self, config: LegraConfig, knowledge_base_id: str):
        """
        Initialize the LEGRA provider

        Args:
            config: LEGRA configuration
            knowledge_base_id: Knowledge base identifier
        """
        super().__init__(knowledge_base_id)
        self.config = config
        self.legra_instance: Optional[Legra] = None
        self.data_path = f"legra_data/{knowledge_base_id}"

    def initialize(self) -> bool:
        """Initialize the LEGRA system"""
        try:
            # Ensure data directory exists

            chunker = SemanticChunker(
                min_sents=self.config.min_sents,
                max_sents=self.config.max_sents,
                min_sent_length=self.config.min_sent_length
            )

            embedder = SentenceTransformerEmbedder(
                model_name=self.config.embedding_model)
            indexer = FaissFlatIndexer(
                dim=embedder.dimension, use_gpu=self.config.use_gpu)

            clusterer = LeidenClusterer(
                resolution_parameter=self.config.cluster_resolution)
            generator = HuggingFaceGenerator(
                model_name=self.config.generator_model_name,
                device="cuda" if self.config.use_gpu else "cpu",
                truncate_context_size=self.config.max_tokens,
            )
            # Create LEGRA instance
            self.legra_instance = Legra(
                doc_folder="",               # we load files from memory, not disk
                chunker=chunker,
                embedder=embedder,
                indexer=indexer,
                clusterer=clusterer,
                generator=generator,
                max_tokens=self.config.max_tokens,
            )

            self._initialized = True
            logger.info(
                f"LEGRA provider initialized for KB {self.knowledge_base_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize LEGRA provider: {e}")
            return False

    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """Add a document to LEGRA"""
        if not self._initialized or self.legra_instance is None:
            logger.error("LEGRA provider not initialized")
            return False

        try:
            if metadata is None:
                metadata = {}

            # Add knowledge base ID to metadata
            metadata["kb_id"] = self.knowledge_base_id
            metadata["doc_id"] = doc_id

            # Add document to LEGRA
            self.legra_instance.add_document(
                doc_id, extracted_text=content, metadata=metadata)

            logger.info(f"Added document {doc_id} to LEGRA")

            return True

        except Exception as e:
            logger.error(f"Failed to add document {doc_id} to LEGRA: {e}")
            return False

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from LEGRA"""
        if not self._initialized or self.legra_instance is None:
            logger.error("LEGRA provider not initialized")
            return False

        try:
            self.legra_instance.delete_document(doc_id)

            logger.warning(
                f"LEGRA doesn't support direct document deletion for {doc_id}")
            return False

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id} from LEGRA: {e}")
            return False

    async def get_document_ids(self) -> List[str]:
        """Get all document IDs in LEGRA"""
        if not self._initialized or self.legra_instance is None:
            logger.error("LEGRA provider not initialized")
            return []

        try:
            ids = [m["doc_id"] for m in self.legra_instance.docs_meta if m.get(
                "kb_id") == self.knowledge_base_id]
            return list(dict.fromkeys(ids))

        except Exception as e:
            logger.error(f"Failed to get document IDs from LEGRA: {e}")
            return []

    async def search(
        self,
        query: str,
        limit: int = 5,
        mode: str = "local",
        **kwargs
    ) -> List[SearchResult]:
        """Search using LEGRA graph-based retrieval"""
        if not self._initialized or self.legra_instance is None:
            logger.error("LEGRA provider not initialized")
            return []

        try:
            self.legra_instance = Legra.load(str(self.knowledge_base_id))
            results = self.legra_instance.query(query, mode=mode, generate=False)

            # Convert LEGRA results to SearchResult format
            search_results = []
            if results:
                # LEGRA returns a single result string or structured data
                if isinstance(results, str):
                    # Single text result
                    search_result = SearchResult(
                        id=f"legra_result_{len(search_results)}",
                        content=results,
                        metadata={
                            "kb_id": self.knowledge_base_id,
                            "search_mode": mode,
                            "provider": "legra"
                        },
                        score=1.0,  # LEGRA doesn't provide explicit scores
                        source="legra",
                        chunk_count=1
                    )
                    search_results.append(search_result)

                elif isinstance(results, list):
                    # Multiple results
                    for i, result in enumerate(results[:limit]):
                        search_result = SearchResult(
                            id=f"legra_result_{i}",
                            content=str(result),
                            metadata={
                                "kb_id": self.knowledge_base_id,
                                "search_mode": mode,
                                "provider": "legra",
                                "result_index": i
                            },
                            score=1.0 - (i * 0.1),  # Decrease score by rank
                            source="legra",
                            chunk_count=1
                        )
                        search_results.append(search_result)

                elif isinstance(results, dict):
                    # Structured result
                    content = results.get("answer", str(results))
                    search_result = SearchResult(
                        id="legra_structured_result",
                        content=content,
                        metadata={
                            "kb_id": self.knowledge_base_id,
                            "search_mode": mode,
                            "provider": "legra",
                            "raw_result": results
                        },
                        score=1.0,
                        source="legra",
                        chunk_count=1
                    )
                    search_results.append(search_result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to search LEGRA: {e}")
            return []

    async def finalize(self) -> bool:
        """Finalize LEGRA after adding all documents"""
        if not self._initialized or self.legra_instance is None:
            logger.error("LEGRA provider not initialized")
            return False

        try:
            # Build the graph and clusters
            self.legra_instance = Legra.load(str(self.knowledge_base_id), load_reason="finalize")
            self.legra_instance.clusterer =  LeidenClusterer(resolution_parameter=0.5)
            self.legra_instance.complete_index_graph(
                str(self.knowledge_base_id))
            return True

        except Exception as e:
            logger.error(f"Failed to finalize LEGRA: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the LEGRA provider"""
        stats = {
            "provider_type": "legra",
            "knowledge_base_id": self.knowledge_base_id,
            "data_path": self.data_path,
            "initialized": self._initialized
        }

        if self._initialized and self.legra_instance:
            try:
                # Get LEGRA-specific stats
                stats.update({"num_docs": len(self.legra_instance.docs_meta)})
            except Exception as e:
                logger.error(f"Failed to get LEGRA stats: {e}")

        return stats

    def close(self):
        """Clean up LEGRA resources"""
        if self.legra_instance:
            # LEGRA cleanup if needed
            pass
