"""
Vector Provider Implementation

Implements the BaseDataProvider interface for vector-based search using
chunking, embedding, and vector database components.
"""

import logging
from typing import List, Dict, Any, Union, cast
from .db import SearchResult as DBSearchResult
from ..base import BaseDataProvider
from ..models import SearchResult
from .config import VectorConfig
from .embedding.base import BaseEmbedder
from .db.base import BaseVectorDB
from .chunking.base import BaseChunker

logger = logging.getLogger(__name__)


class VectorProvider(BaseDataProvider):
    """
    Orchestrates chunking, embedding, and vector database operations
    based on knowledge base configuration
    """
    name = "vector"
    embedder: BaseEmbedder
    vector_db: BaseVectorDB
    chunker: BaseChunker

    def __init__(
        self,
        config: VectorConfig,
        knowledge_base_id: str
    ):
        super().__init__(knowledge_base_id)
        self.config = config

    async def initialize(self) -> bool:
        """Initialize all components"""
        self.embedder = self.config.embedding.get()
        self.vector_db = self.config.vector_db.get()
        self.chunker = self.config.chunking.get()
        try:
            # Initialize embedder
            if not await self.embedder.initialize():
                logger.error("Failed to initialize embedder")
                return False

            # Initialize vector database
            if not await self.vector_db.initialize():
                logger.error("Failed to initialize vector database")
                return False

            # Create collection with the right dimension
            dimension = await self.embedder.get_dimension()
            if not await self.vector_db.create_collection(dimension):
                logger.error("Failed to create vector database collection")
                return False

            # Set embedding function for ChromaDB if needed
            if hasattr(self.vector_db, 'set_embedding_function'):
                # Create a wrapper function for LangChain compatibility
                async def embedding_function(texts):
                    if isinstance(texts, str):
                        return await self.embedder.embed_text(texts)
                    return await self.embedder.embed_texts(texts)

                self.vector_db.set_embedding_function(embedding_function)

            self._initialized = True
            logger.info("VectorProvider initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize VectorProvider: {e}")
            return False

    async def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Union[Dict[str, Any], None] = None
    ) -> bool:
        """
        Add a document to the vector store

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

            # Add knowledge base ID to metadata
            if metadata is None:
                metadata = {}
            metadata["kb_id"] = self.knowledge_base_id
            metadata["doc_id"] = doc_id

            # Delete existing document first
            await self.delete_document(doc_id)

            # Chunk the document
            chunks = self.chunker.chunk_text(content, metadata)
            if not chunks:
                logger.warning(f"No chunks created for document {doc_id}")
                return False

            # Generate embeddings for chunks
            chunk_texts = [chunk.content for chunk in chunks]
            embeddings = await self.embedder.embed_texts(chunk_texts)

            if len(embeddings) != len(chunks):
                logger.error(f"Embedding count mismatch for document {doc_id}")
                return False

            # Prepare data for vector database
            chunk_ids = [f"{doc_id}_chunk_{chunk.index}" for chunk in chunks]
            chunk_metadatas = [chunk.metadata for chunk in chunks]

            # Add to vector database
            success = await self.vector_db.add_vectors(
                ids=chunk_ids,
                vectors=embeddings,
                metadatas=chunk_metadatas,
                contents=chunk_texts
            )

            if success:
                logger.info(
                    f"Added document {doc_id} with {len(chunks)} chunks")
            else:
                logger.error(
                    f"Failed to add document {doc_id} to vector database")

            return success

        except Exception as e:
            logger.error(f"Failed to add document {doc_id}: {e}")
            return False

    async def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the vector store

        Args:
            doc_id: Document identifier

        Returns:
            Success status
        """
        try:
            if not self._initialized:
                if not await self.initialize():
                    return False

            # Get all chunk IDs for this document
            all_ids = await self.vector_db.get_all_ids({"doc_id": doc_id})

            if all_ids:
                success = await self.vector_db.delete_vectors(all_ids)
                if success:
                    logger.info(
                        f"Deleted document {doc_id} with {len(all_ids)} chunks")
                return success
            else:
                logger.info(f"No chunks found for document {doc_id}")
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
        Search the vector store

        Args:
            query: Search query
            limit: Maximum number of results
            filter_dict: Optional metadata filters

        Returns:
            List of search results
        """
        try:
            if not self._initialized:
                if not await self.initialize():
                    return []

            if not query.strip():
                return []

            # Add knowledge base filter if not provided
            if filter_dict is None:
                filter_dict = {}
            if self.knowledge_base_id and "kb_id" not in filter_dict:
                filter_dict["kb_id"] = self.knowledge_base_id

            # Generate query embedding
            query_embedding = await self.embedder.embed_query(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            # Search vector database
            search_results = await self.vector_db.search(
                query_vector=query_embedding,
                # Get more results to consolidate chunks
                limit=limit * 3,
                filter_dict=filter_dict,
            )

            # Group results by document and consolidate chunks
            doc_results = self._consolidate_chunks(search_results, limit)

            # Convert to SearchResult format
            formatted_results = []
            for doc_result in doc_results:
                search_result = SearchResult(
                    id=doc_result["doc_id"],
                    content=doc_result["content"],
                    metadata=doc_result["metadata"],
                    score=doc_result["score"],
                    source="vector",
                    chunk_count=doc_result["chunk_count"]
                )
                formatted_results.append(search_result)

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search vector store: {e}")
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

            # Get all IDs with knowledge base filter
            all_ids = await self.vector_db.get_all_ids({"kb_id": filter_kb_id})

            # Extract unique document IDs (remove chunk suffixes)
            doc_ids = set()
            for chunk_id in all_ids:
                if "_chunk_" in chunk_id:
                    doc_id = chunk_id.split("_chunk_")[0]
                    doc_ids.add(doc_id)
                else:
                    doc_ids.add(chunk_id)

            return list(doc_ids)

        except Exception as e:
            logger.error(f"Failed to get document IDs: {e}")
            return []

    def _consolidate_chunks(self, search_results: List[DBSearchResult], limit: int) -> List[Dict[str, Any]]:
        """
        Consolidate search results by document, combining chunks

        Args:
            search_results: List of search results
            limit: Maximum number of documents to return

        Returns:
            List of consolidated document results
        """
        doc_groups: Dict[str, Dict[str, Any]] = {}

        # Group chunks by document ID
        for result in search_results:
            doc_id = result.metadata.get("doc_id", "unknown")

            if doc_id not in doc_groups:
                doc_groups[doc_id] = {
                    "chunks": [],
                    "best_score": result.score,
                    "metadata": {k: v for k, v in result.metadata.items()
                                 if k not in ["chunk_index", "chunk_id", "start_char", "end_char"]}
                }

            chunks_list = cast(List[Dict[str, Any]],
                               doc_groups[doc_id]["chunks"])
            chunks_list.append({
                "content": result.content,
                "score": result.score,
                "chunk_index": result.metadata.get("chunk_index", 0)
            })

            # Update best score
            current_best = cast(float, doc_groups[doc_id]["best_score"])
            if result.score > current_best:
                doc_groups[doc_id]["best_score"] = result.score

        # Consolidate and sort
        consolidated_results = []
        for doc_id, data in doc_groups.items():
            # Sort chunks by index
            chunks_data = cast(List[Dict[str, Any]], data["chunks"])
            sorted_chunks = sorted(chunks_data, key=lambda x: x["chunk_index"])

            # Combine content
            combined_content = "\n".join(
                [chunk["content"] for chunk in sorted_chunks])

            consolidated_results.append({
                "doc_id": doc_id,
                "content": combined_content,
                "metadata": data["metadata"],
                "score": data["best_score"],
                "chunk_count": len(sorted_chunks)
            })

        # Sort by score and limit
        consolidated_results.sort(key=lambda x: x["score"], reverse=True)
        return consolidated_results[:limit]

    def close(self):
        """Close database connections"""
        if self.vector_db:
            self.vector_db.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector provider"""
        return {
            "provider_type": "vector",
            "knowledge_base_id": self.knowledge_base_id,
            "initialized": self._initialized
        }
