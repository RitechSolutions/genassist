"""
ChromaDB vector database implementation
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from chromadb import AsyncHttpClient, AsyncClientAPI
from langchain_chroma import Chroma


from .base import BaseVectorDB, VectorDBConfig, SearchResult

logger = logging.getLogger(__name__)


class ChromaVectorDB(BaseVectorDB):
    """ChromaDB vector database provider"""
    chroma_client: Optional[AsyncClientAPI]
    langchain_store: Optional[Chroma]
    embedding_function: Optional[Callable[[str], List[float]]]

    def __init__(self, config: VectorDBConfig):
        super().__init__(config)

    async def initialize(self) -> bool:
        """Initialize the ChromaDB connection"""
        try:
            # Initialize ChromaDB client
            if self.config.host and self.config.port:
                # Remote ChromaDB with async client
                self.chroma_client = await AsyncHttpClient(
                    host=self.config.host,
                    port=self.config.port,
                )
            else:
                raise ValueError(
                    "Host and port must be provided for remote ChromaDB")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            return False

    def set_embedding_function(self, embedding_function):
        """Set the embedding function for LangChain integration"""
        self.embedding_function = embedding_function

        if self.chroma_client and self.embedding_function:
            # Initialize LangChain Chroma store
            self.langchain_store = Chroma(
                client=self.chroma_client,
                collection_name=self.config.collection_name,
                embedding_function=self.embedding_function
            )

    async def create_collection(self, dimension: int) -> bool:
        """Create a new collection"""
        try:
            if not self.chroma_client:
                if not await self.initialize():
                    return False

            # ChromaDB creates collections automatically when accessed
            # Just verify we can get/create the collection
            metadata = {
                "hnsw:space": self.config.distance_metric,
                "hnsw:M": self.config.hnsw_m,
                "hnsw:construction_ef": self.config.hnsw_ef_construction,
                "hnsw:search_ef": self.config.hnsw_ef_search,
            }
            metadata.update(self.config.extra_params)

            # Use async method for all clients
            self.collection = await self.chroma_client.get_or_create_collection(
                name=self.config.collection_name,
                metadata=metadata
            )

            logger.info(
                f"Created/accessed ChromaDB collection: {self.config.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create ChromaDB collection: {e}")
            return False

    async def delete_collection(self) -> bool:
        """Delete the collection"""
        try:
            if not self.chroma_client:
                return True  # Nothing to delete

            # Use async method for all clients
            await self.chroma_client.delete_collection(self.config.collection_name)

            self.collection = None
            self.langchain_store = None

            logger.info(
                f"Deleted ChromaDB collection: {self.config.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete ChromaDB collection: {e}")
            return False

    async def add_vectors(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
        contents: List[str]
    ) -> bool:
        """Add vectors to the collection"""
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return False

            # Use async method for all clients
            await self.collection.add(
                ids=ids,
                embeddings=vectors,
                metadatas=metadatas,
                documents=contents
            )

            logger.info(f"Added {len(ids)} vectors to ChromaDB collection")
            return True

        except Exception as e:
            logger.error(f"Failed to add vectors to ChromaDB: {e}")
            return False

    async def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors by IDs"""
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return False

            # Check which IDs exist first
            existing_results = await self.collection.get(ids=ids)

            existing_ids = existing_results["ids"]

            if existing_ids:
                await self.collection.delete(ids=existing_ids)

                logger.info(
                    f"Deleted {len(existing_ids)} vectors from ChromaDB")

            return True

        except Exception as e:
            logger.error(f"Failed to delete vectors from ChromaDB: {e}")
            return False

    async def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filter_dict: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """Search for similar vectors"""
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return []

            # Use ChromaDB query with async for all clients
            results = await self.collection.query(
                query_embeddings=[query_vector],
                n_results=limit,
                where=filter_dict,
                include=["documents", "metadatas", "distances"]
            )

            # Convert to SearchResult objects
            search_results = []
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    result = SearchResult(
                        id=results["ids"][0][i],
                        content=results["documents"][0][i] if results["documents"] else "",
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {
                        },
                        score=None,  # Will be calculated from distance
                        distance=results["distances"][0][i] if results["distances"] else 0.0
                    )
                    search_results.append(result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to search ChromaDB: {e}")
            return []

    async def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Get vectors by their IDs"""
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return []

            # Use async method for all clients
            results = await self.collection.get(
                ids=ids,
                include=["documents", "metadatas"]
            )

            # Convert to SearchResult objects
            search_results = []
            if results["ids"]:
                for i, doc_id in enumerate(results["ids"]):
                    result = SearchResult(
                        id=doc_id,
                        content=results["documents"][i] if results["documents"] else "",
                        metadata=results["metadatas"][i] if results["metadatas"] else {
                        },
                        score=1.0,  # No distance for direct retrieval
                        distance=0.0
                    )
                    search_results.append(result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to get vectors by IDs from ChromaDB: {e}")
            return []

    async def get_all_ids(self, filter_dict: Dict[str, Any] = None) -> List[str]:
        """Get all document IDs in the collection"""
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return []

            # Use async method for all clients
            results = await self.collection.get(
                where=filter_dict,
                include=[]  # Only IDs
            )

            return results["ids"] if results["ids"] else []

        except Exception as e:
            logger.error(f"Failed to get all IDs from ChromaDB: {e}")
            return []

    async def count(self, filter_dict: Dict[str, Any] = None) -> int:
        """Count documents in the collection"""
        try:
            if not self.collection:
                logger.error("Collection not initialized")
                return 0

            # ChromaDB doesn't have a direct count method, so we get all IDs
            # Use async method for all clients
            results = await self.collection.get(
                where=filter_dict,
                include=[]  # Only IDs
            )

            return len(results["ids"]) if results["ids"] else 0

        except Exception as e:
            logger.error(f"Failed to count documents in ChromaDB: {e}")
            return 0
