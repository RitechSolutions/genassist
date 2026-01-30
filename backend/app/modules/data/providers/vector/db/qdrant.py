"""
Qdrant vector database implementation
"""

import logging
import os
import hashlib
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    HnswConfigDiff,
)

from .base import BaseVectorDB, VectorDBConfig, SearchResult

logger = logging.getLogger(__name__)

# Default Qdrant connection settings from environment
DEFAULT_QDRANT_HOST = os.getenv("QDRANT_HOST", "http://localhost")
DEFAULT_QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))


def _sanitize_qdrant_id(doc_id: str) -> str:
    """
    Sanitize document ID for Qdrant.
    Qdrant point IDs can be integers, UUIDs, or strings without certain special characters.
    We hash the ID to create a valid UUID-like string.
    """
    # Create a deterministic hash of the ID
    # Use SHA256 and take first 32 chars to create a UUID-like string
    hash_obj = hashlib.sha256(doc_id.encode('utf-8'))
    hash_hex = hash_obj.hexdigest()[:32]
    # Format as UUID-like string (8-4-4-4-12)
    return f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"


class QdrantVectorDB(BaseVectorDB):
    """Qdrant vector database provider"""

    def __init__(self, config: VectorDBConfig):
        super().__init__(config)
        self.client: Optional[AsyncQdrantClient] = None
        self.collection_name: str = config.collection_name

    async def initialize(self) -> bool:
        """Initialize the Qdrant connection"""
        try:
            # Initialize Qdrant client
            # if self.config.host and self.config.port:
            # Remote Qdrant with async client
            url = f"{DEFAULT_QDRANT_HOST}:{DEFAULT_QDRANT_PORT}"
            logger.info(f"Connecting to Qdrant at: {url}")
            self.client = AsyncQdrantClient(url=url)

            # Test connection - try to get collections, but don't fail if it errors
            # (server might be running but endpoint might be different, or it's a new server)
            # The actual operations will fail later if there's a real connection issue
            if self.client:
                try:
                    await self.client.get_collections()
                    logger.debug("Qdrant connection test successful")
                except Exception as test_error:
                    # Log warning but don't fail - the connection might still work
                    # Common for new servers or if endpoint structure differs
                    error_msg = str(test_error)
                    if "404" in error_msg or "Not Found" in error_msg:
                        logger.debug(
                            f"Qdrant connection test returned 404 (server may be new or endpoint differs): {test_error}"
                        )
                    else:
                        logger.warning(f"Qdrant connection test failed: {test_error}")

            logger.info(f"Initialized Qdrant connection: {self.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")
            return False

    def _get_distance_metric(self) -> Distance:
        """Convert config distance metric to Qdrant Distance enum"""
        metric_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot_product": Distance.DOT,
        }
        return metric_map.get(self.config.distance_metric, Distance.COSINE)

    async def create_collection(self, dimension: int) -> bool:
        """Create a new collection"""
        try:
            if not self.client:
                if not await self.initialize():
                    return False

            if not self.client:
                logger.error("Qdrant client not initialized")
                return False

            # Validate collection name
            if not self.collection_name or not self.collection_name.strip():
                logger.error("Qdrant collection name is empty or invalid")
                return False

            # Check if collection already exists
            collection_exists = False
            try:
                collections = await self.client.get_collections()
                collection_names = [col.name for col in collections.collections]
                collection_exists = self.collection_name in collection_names
            except Exception as get_error:
                # If get_collections fails, try to get the specific collection
                # This handles cases where the server is new or endpoint differs
                logger.debug(
                    f"Could not list collections, checking specific collection: {get_error}"
                )
                try:
                    collection_info = await self.client.get_collection(
                        self.collection_name
                    )
                    collection_exists = collection_info is not None
                except Exception as get_collection_error:
                    # Collection doesn't exist, which is fine - we'll create it
                    error_msg = str(get_collection_error)
                    if "404" not in error_msg and "Not Found" not in error_msg:
                        logger.debug(
                            f"Collection check returned: {get_collection_error}"
                        )
                    collection_exists = False

            if not collection_exists:
                # Create new collection
                distance = self._get_distance_metric()

                # Build vector params with HNSW configuration if specified
                vector_params = VectorParams(
                    size=dimension,
                    distance=distance,
                )

                # Add HNSW parameters if index_type is hnsw
                if self.config.index_type == "hnsw":
                    # Qdrant uses hnsw_config parameter
                    extra_params = self.config.extra_params or {}
                    hnsw_config_dict = extra_params.get(
                        "hnsw_config",
                        {
                            "m": self.config.hnsw_m,
                            "ef_construct": self.config.hnsw_ef_construction,
                            "full_scan_threshold": 10000,
                        },
                    )
                    # Create proper HnswConfigDiff object to avoid Pydantic serialization warnings
                    vector_params.hnsw_config = HnswConfigDiff(**hnsw_config_dict)

                logger.info(
                    f"Creating Qdrant collection '{self.collection_name}' with dimension {dimension} and distance metric {self.config.distance_metric}"
                )
                try:
                    await self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=vector_params,
                    )
                    logger.info(
                        f"Successfully created Qdrant collection: {self.collection_name}"
                    )
                except Exception as create_error:
                    error_msg = str(create_error)
                    # Check if it's a 404 - might indicate server issue or wrong endpoint
                    if "404" in error_msg or "Not Found" in error_msg:
                        logger.error(
                            f"Failed to create Qdrant collection '{self.collection_name}': 404 Not Found. "
                            f"This might indicate: 1) Qdrant server is not running, 2) Wrong URL/port, "
                            f"3) API version mismatch. Error: {create_error}"
                        )
                    else:
                        logger.error(
                            f"Failed to create Qdrant collection '{self.collection_name}': {create_error}"
                        )
                    raise
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")

            return True

        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {e}")
            return False

    async def delete_collection(self) -> bool:
        """Delete the collection"""
        try:
            if not self.client:
                return True  # Nothing to delete

            await self.client.delete_collection(self.collection_name)

            self.collection = None

            logger.info(f"Deleted Qdrant collection: {self.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete Qdrant collection: {e}")
            return False

    async def add_vectors(
        self,
        ids: List[str],
        vectors: List[List[float]],
        metadatas: List[Dict[str, Any]],
        contents: List[str],
    ) -> bool:
        """Add vectors to the collection"""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return False

            # Prepare points for Qdrant
            points = []
            for doc_id, vector, metadata, content in zip(
                ids, vectors, metadatas, contents
            ):
                # Sanitize ID for Qdrant (hash to create valid UUID-like string)
                qdrant_id = _sanitize_qdrant_id(doc_id)
                
                # Qdrant stores content in payload
                # Also store original ID in payload for retrieval
                payload = metadata.copy()
                payload["content"] = content
                payload["_original_id"] = doc_id  # Store original ID for mapping back

                point = PointStruct(id=qdrant_id, vector=vector, payload=payload)
                points.append(point)

            # Upsert points (insert or update)
            await self.client.upsert(
                collection_name=self.collection_name, points=points
            )

            logger.info(f"Added {len(ids)} vectors to Qdrant collection")
            return True

        except Exception as e:
            logger.error(f"Failed to add vectors to Qdrant: {e}")
            return False

    async def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors by IDs"""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return False

            if not ids:
                return True

            # Convert original IDs to sanitized Qdrant IDs
            qdrant_ids = [_sanitize_qdrant_id(doc_id) for doc_id in ids]
            
            await self.client.delete(
                collection_name=self.collection_name, points_selector=qdrant_ids
            )

            logger.info(f"Deleted {len(ids)} vectors from Qdrant collection")
            return True

        except Exception as e:
            logger.error(f"Failed to delete vectors from Qdrant: {e}")
            return False

    def _build_qdrant_filter(
        self, filter_dict: Optional[Dict[str, Any]]
    ) -> Optional[Filter]:
        """Convert filter_dict to Qdrant Filter"""
        if not filter_dict:
            return None

        conditions = []
        for key, value in filter_dict.items():
            condition = FieldCondition(key=key, match=MatchValue(value=value))
            conditions.append(condition)

        if conditions:
            return Filter(must=conditions)
        return None

    async def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search for similar vectors"""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return []

            # Build Qdrant filter
            qdrant_filter = self._build_qdrant_filter(filter_dict)

            # Perform search using query_points (async client uses query_points instead of search)
            query_response = await self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
            )

            # Extract results from QueryResponse
            search_results_qdrant = query_response.points

            # Convert to SearchResult objects
            search_results = []
            for point in search_results_qdrant:
                # ScoredPoint has id, score, and payload attributes
                payload = point.payload if point.payload else {}
                if not isinstance(payload, dict):
                    payload = {}
                
                # Extract original ID from payload (we stored it there)
                original_id = payload.pop("_original_id", None)
                # Use original ID if available, otherwise use Qdrant ID
                result_id = original_id if original_id else str(point.id)
                
                # Extract content from payload (we stored it there)
                content = payload.pop("content", "") if isinstance(payload, dict) else ""

                # Qdrant returns score (similarity), we need to convert to distance
                # For cosine: score is similarity (higher is better), distance = 1 - score
                # For euclidean: score is already distance (lower is better)
                # For dot: score is similarity (higher is better), distance = 1 - score
                score = point.score
                if self.config.distance_metric == "cosine":
                    distance = 1.0 - score if score <= 1.0 else 0.0
                elif self.config.distance_metric == "euclidean":
                    distance = score
                else:  # dot_product
                    distance = 1.0 - score if score <= 1.0 else 0.0

                search_result = SearchResult(
                    id=result_id,
                    content=content,
                    metadata=payload,
                    score=None,  # Will be calculated from distance
                    distance=distance,
                )
                search_results.append(search_result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to search Qdrant: {e}")
            return []

    async def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Get vectors by their IDs"""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return []

            if not ids:
                return []

            # Convert original IDs to sanitized Qdrant IDs
            qdrant_ids = [_sanitize_qdrant_id(doc_id) for doc_id in ids]
            
            points = await self.client.retrieve(
                collection_name=self.collection_name,
                ids=qdrant_ids,
                with_payload=True,
                with_vectors=False,
            )

            # Convert to SearchResult objects
            search_results = []
            for point in points:
                payload = point.payload or {}
                if not isinstance(payload, dict):
                    payload = {}
                
                # Extract original ID from payload
                original_id = payload.pop("_original_id", None)
                result_id = original_id if original_id else str(point.id)
                
                content = payload.pop("content", "")

                search_result = SearchResult(
                    id=result_id,
                    content=content,
                    metadata=payload,
                    score=1.0,  # No distance for direct retrieval
                    distance=0.0,
                )
                search_results.append(search_result)

            return search_results

        except Exception as e:
            logger.error(f"Failed to get vectors by IDs from Qdrant: {e}")
            return []

    async def get_all_ids(
        self, filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Get all document IDs in the collection"""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return []

            # Build Qdrant filter
            qdrant_filter = self._build_qdrant_filter(filter_dict)

            # Scroll through all points
            all_ids = []
            offset = None
            limit_scroll = 100  # Batch size for scrolling

            while True:
                scroll_result = await self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qdrant_filter,
                    limit=limit_scroll,
                    offset=offset,
                    with_payload=True,  # Need payload to get original IDs
                    with_vectors=False,
                )

                points = scroll_result[0]
                if not points:
                    break

                # Extract original IDs from payload, fallback to Qdrant ID
                for point in points:
                    payload = point.payload if point.payload else {}
                    original_id = payload.get("_original_id") if isinstance(payload, dict) else None
                    all_ids.append(original_id if original_id else str(point.id))
                
                offset = scroll_result[1]  # Next offset

                if offset is None:
                    break

            return all_ids

        except Exception as e:
            logger.error(f"Failed to get all IDs from Qdrant: {e}")
            return []

    async def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Count documents in the collection"""
        try:
            if not self.client:
                logger.error("Client not initialized")
                return 0

            # Build Qdrant filter
            qdrant_filter = self._build_qdrant_filter(filter_dict)

            # Get collection info
            collection_info = await self.client.get_collection(self.collection_name)

            # If no filter, return total points count
            if not qdrant_filter:
                return collection_info.points_count

            # With filter, we need to scroll and count
            # This is less efficient but necessary for filtered counts
            count = 0
            offset = None
            limit_scroll = 100

            while True:
                scroll_result = await self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=qdrant_filter,
                    limit=limit_scroll,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False,
                )

                points = scroll_result[0]
                if not points:
                    break

                count += len(points)
                offset = scroll_result[1]

                if offset is None:
                    break

            return count

        except Exception as e:
            logger.error(f"Failed to count documents in Qdrant: {e}")
            return 0

    def close(self):
        """Close the database connection"""
        # Qdrant client doesn't require explicit closing for async client
        # Just clear the reference
        self.client = None
        logger.debug("Closed Qdrant connection")
