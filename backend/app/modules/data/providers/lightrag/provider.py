"""
LightRAG Provider Implementation

Implements the BaseDataProvider interface for LightRAG-based graph search.
"""

import logging
import os
import re
from typing import List, Dict, Any, Optional
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_embed, gpt_4o_mini_complete
from lightrag.kg.shared_storage import initialize_pipeline_status

from .config import LightRAGConfig
from ..base import FinalizableProvider, SearchResult
from app.core.project_path import DATA_VOLUME

logger = logging.getLogger(__name__)


class LightRAGProvider(FinalizableProvider):
    """
    LightRAG provider for graph-based retrieval and generation

    This provider handles:
    - Graph-based document storage with knowledge graphs
    - Embedding-based retrieval with LLM completion
    - Multiple search modes (local, global, mix)
    - Async document operations and search
    """
    name = "lightrag"
    
    def __init__(self, config: LightRAGConfig, knowledge_base_id: str):
        """
        Initialize the LightRAG provider

        Args:
            config: LightRAG configuration
            knowledge_base_id: Knowledge base identifier
        """
        super().__init__(knowledge_base_id)
        self.config = config
        self.rag: Optional[LightRAG] = None
        self._document_map: Dict[str, str] = {}  # Map to track document IDs to content
        self.working_dir = str(DATA_VOLUME / config.working_dir)

        # Get embedding and LLM functions based on config
        self.embedding_func = self._get_embedding_func(config.embedding_func_name)
        self.llm_model_func = self._get_llm_model_func(config.llm_model_func_name)

    def _get_embedding_func(self, func_name: str):
        """Get embedding function by name"""
        if func_name == "openai_embed":
            return openai_embed
        # Add other embedding functions as needed
        return openai_embed

    def _get_llm_model_func(self, func_name: str):
        """Get LLM model function by name"""
        if func_name == "gpt_4o_mini_complete":
            return gpt_4o_mini_complete
        # Add other LLM functions as needed
        return gpt_4o_mini_complete

    async def initialize(self) -> bool:
        """Initialize the LightRAG system"""
        try:
            # Ensure the working directory exists within the DATA_VOLUME
            os.makedirs(self.working_dir, exist_ok=True)

            # Initialize LightRAG asynchronously
            self.rag = await self._initialize_rag()

            self._initialized = True
            logger.info(f"LightRAG provider initialized for KB {self.knowledge_base_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize LightRAG provider: {e}")
            return False

    async def _initialize_rag(self) -> LightRAG:
        """Async helper to initialize LightRAG"""
        # Prepare vector db storage kwargs
        vector_db_kwargs = self.config.vector_db_storage_cls_kwargs.copy()
        vector_db_kwargs["local_path"] = self.working_dir

        rag = LightRAG(
            working_dir=self.working_dir,
            embedding_func=self.embedding_func,
            llm_model_func=self.llm_model_func,
            chunk_token_size=self.config.chunk_token_size,
            chunk_overlap_token_size=self.config.chunk_overlap_token_size,
            vector_storage=self.config.vector_storage,
            log_level=self.config.log_level,
            embedding_batch_num=self.config.embedding_batch_num,
            vector_db_storage_cls_kwargs=vector_db_kwargs,
        )

        logger.info("=============== entered initialize storages ================")
        await rag.initialize_storages()
        logger.info("=============== finished initialize storages ================")

        logger.info("=============== entered initialize pipeline status ================")
        await initialize_pipeline_status()
        logger.info("=============== finished initialize pipeline status ================")

        return rag

    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a document to LightRAG"""
        if not self._initialized or self.rag is None:
            logger.error("LightRAG provider not initialized")
            return False

        try:
            if metadata is None:
                metadata = {}

            # Add knowledge base ID to metadata
            metadata["kb_id"] = self.knowledge_base_id
            metadata["doc_id"] = doc_id

            # Track document in our map
            self._document_map[doc_id] = content

            # Format document with metadata for LightRAG
            metadata_str = str(metadata)
            document_with_metadata = f"{metadata_str}\n\n{content}"

            # Insert document asynchronously
            logger.info(f"Adding document {doc_id} to LightRAG")
            await self.rag.ainsert(document_with_metadata)

            logger.info(f"Added document {doc_id} to LightRAG")
            return True

        except Exception as e:
            logger.error(f"Failed to add document {doc_id} to LightRAG: {e}")
            return False

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document from LightRAG"""
        if not self._initialized or self.rag is None:
            logger.error("LightRAG provider not initialized")
            return False

        try:
            # Check if we have this document
            if doc_id in self._document_map:
                # Remove from our tracking map
                self._document_map.pop(doc_id)
                logger.info(f"Removed document {doc_id} from tracking map")

                # Note: LightRAG doesn't support direct document deletion
                # The document will remain in the graph but won't be tracked
                logger.warning(f"LightRAG doesn't support direct document deletion for {doc_id}")
            else:
                logger.info(f"No document found with ID {doc_id} to delete")

            return True

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id} from LightRAG: {e}")
            return False

    async def get_document_ids(self) -> List[str]:
        """Get all document IDs in LightRAG for this knowledge base"""
        if not self._initialized or self.rag is None:
            logger.error("LightRAG provider not initialized")
            return []

        try:
            # Return document IDs from our tracking map that belong to this KB
            kb_prefix = f"KB:{self.knowledge_base_id}#"
            doc_ids = [
                doc_id for doc_id in self._document_map.keys()
                if doc_id.startswith(kb_prefix) or doc_id in self._document_map
            ]

            # If we don't have specific KB-prefixed IDs, return all tracked IDs
            if not doc_ids:
                doc_ids = list(self._document_map.keys())

            logger.info(f"Found {len(doc_ids)} documents for knowledge base {self.knowledge_base_id}")
            return doc_ids

        except Exception as e:
            logger.error(f"Failed to get document IDs from LightRAG: {e}")
            return []

    async def search(
        self,
        query: str,
        limit: int = 5,
        mode: Optional[str] = None,
        **kwargs
    ) -> List[SearchResult]:
        """Search using LightRAG graph-based retrieval"""
        if not self._initialized or self.rag is None:
            logger.error("LightRAG provider not initialized")
            return []

        try:
            # Use configured search mode if not specified
            search_mode = mode or self.config.search_mode

            # Create query parameters
            param = QueryParam(
                mode=search_mode,
                top_k=min(limit, self.config.top_k),
                response_type=self.config.response_type
            )

            logger.info("=============== entered search documents ================")
            logger.info(f"Searching with query: {query}, mode: {search_mode}, limit: {limit}")

            # Perform search asynchronously
            raw_results = await self.rag.aquery(query, param=param)

            logger.info(f"Raw results from LightRAG: {raw_results}")

            # Convert LightRAG results to SearchResult format
            search_results: List[SearchResult] = []
            if raw_results:
                if isinstance(raw_results, str):
                    # Parse the structured response
                    search_results = self._parse_lightrag_response(raw_results, limit)
                elif isinstance(raw_results, list):
                    # Multiple results
                    for i, result in enumerate(raw_results[:limit]):
                        search_result = SearchResult(
                            id=f"lightrag_result_{i}",
                            content=str(result),
                            metadata={
                                "kb_id": self.knowledge_base_id,
                                "search_mode": search_mode,
                                "provider": "lightrag",
                                "result_index": i
                            },
                            score=1.0 - (i * 0.1),  # Decrease score by rank
                            source="lightrag",
                            chunk_count=1
                        )
                        search_results.append(search_result)
                elif isinstance(raw_results, dict):
                    # Structured result
                    content = raw_results.get("answer", str(raw_results))
                    search_result = SearchResult(
                        id="lightrag_structured_result",
                        content=content,
                        metadata={
                            "kb_id": self.knowledge_base_id,
                            "search_mode": search_mode,
                            "provider": "lightrag",
                            "raw_result": raw_results
                        },
                        score=1.0,
                        source="lightrag",
                        chunk_count=1
                    )
                    search_results.append(search_result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to search LightRAG: {e}")
            return []

    def _parse_lightrag_response(self, raw_results: str, limit: int) -> List[SearchResult]:
        """Parse LightRAG structured response into SearchResult objects"""
        search_results: List[SearchResult] = []
        try:
            # Extract titles and content sections
            titles = re.findall(r'^###\s+(.*)', raw_results, re.MULTILINE)

            if titles:
                # Extract content for first title
                content = raw_results.split(titles[0])[1].split("###")[0].strip()

                search_result = SearchResult(
                    id="lightrag_parsed_result",
                    content=content,
                    metadata={
                        "kb_id": self.knowledge_base_id,
                        "provider": "lightrag",
                        "title": titles[0] if titles else "unknown"
                    },
                    score=1.0,
                    source="lightrag",
                    chunk_count=1
                )
                search_results.append(search_result)

            # Always include the full raw result as backup
            search_result_full = SearchResult(
                id="lightrag_full_result",
                content=raw_results,
                metadata={
                    "kb_id": self.knowledge_base_id,
                    "provider": "lightrag",
                    "type": "full_response"
                },
                score=0.9,
                source="lightrag",
                chunk_count=1
            )
            search_results.append(search_result_full)

        except Exception as e:
            logger.error(f"Failed to parse LightRAG response: {e}")
            # Fallback to raw result
            search_result = SearchResult(
                id="lightrag_raw_result",
                content=raw_results,
                metadata={
                    "kb_id": self.knowledge_base_id,
                    "provider": "lightrag",
                    "type": "raw_fallback"
                },
                score=0.8,
                source="lightrag",
                chunk_count=1
            )
            search_results.append(search_result)

        return search_results[:limit]

    async def finalize(self) -> bool:
        """Finalize LightRAG after adding all documents"""
        if not self._initialized or self.rag is None:
            logger.error("LightRAG provider not initialized")
            return False

        try:
            # LightRAG processes documents incrementally, so finalization
            # mainly ensures all pending operations are complete
            logger.info(f"Finalizing LightRAG for KB {self.knowledge_base_id}")

            # Any additional finalization steps can be added here
            # For now, we just confirm the system is ready

            logger.info(f"LightRAG finalization complete for KB {self.knowledge_base_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to finalize LightRAG: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the LightRAG provider"""
        stats = {
            "provider_type": "lightrag",
            "knowledge_base_id": self.knowledge_base_id,
            "working_dir": self.working_dir,
            "initialized": self._initialized,
            "search_mode": self.config.search_mode,
            "chunk_token_size": self.config.chunk_token_size,
            "vector_storage": self.config.vector_storage
        }

        if self._initialized and self.rag:
            try:
                # Get LightRAG-specific stats
                stats.update({
                    "num_docs": len(self._document_map),
                    "tracked_documents": list(self._document_map.keys())[:10]  # Sample
                })
            except Exception as e:
                logger.error(f"Failed to get LightRAG stats: {e}")

        return stats

    def close(self):
        """Clean up LightRAG resources"""
        if self.rag:
            # LightRAG cleanup if needed
            logger.info(f"Closing LightRAG provider for KB {self.knowledge_base_id}")
            # Any specific cleanup operations can be added here

        self._document_map.clear()
