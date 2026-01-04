"""
FAISS vector database implementation
"""

import logging
import os
import pickle
from typing import List, Dict, Any
import numpy as np

from .base import BaseVectorDB, VectorDBConfig, SearchResult

logger = logging.getLogger(__name__)


class FaissVectorDB(BaseVectorDB):
    """FAISS vector database provider"""
    
    def __init__(self, config: VectorDBConfig):
        super().__init__(config)
        self.index = None
        self.id_map = {}  # Maps internal index to document ID
        self.metadata_map = {}  # Maps document ID to metadata
        self.content_map = {}  # Maps document ID to content
        self.dimension = None
        self.next_id = 0
    
    async def initialize(self) -> bool:
        """Initialize the FAISS index"""
        try:
            import faiss
            self.faiss = faiss
            
            # Load existing index if it exists
            if self.config.persist_directory:
                self._load_index()
            
            logger.info("Initialized FAISS vector database")
            return True
            
        except ImportError:
            logger.error("FAISS not installed. Install with: pip install faiss-cpu or faiss-gpu")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize FAISS: {e}")
            return False
    
    async def create_collection(self, dimension: int) -> bool:
        """Create a new FAISS index"""
        try:
            if not self.faiss:
                if not await self.initialize():
                    return False
            
            self.dimension = dimension
            
            # Create index based on configuration
            if self.config.index_type == "flat":
                if self.config.distance_metric == "cosine":
                    # Normalize vectors for cosine similarity
                    self.index = self.faiss.IndexFlatIP(dimension)
                elif self.config.distance_metric == "euclidean":
                    self.index = self.faiss.IndexFlatL2(dimension)
                else:
                    self.index = self.faiss.IndexFlatIP(dimension)  # Default to inner product
            
            elif self.config.index_type == "hnsw":
                # HNSW index for faster search
                if self.config.distance_metric == "cosine":
                    self.index = self.faiss.IndexHNSWFlat(dimension, self.config.hnsw_m)
                    self.index.hnsw.efConstruction = self.config.hnsw_ef_construction
                    self.index.hnsw.efSearch = self.config.hnsw_ef_search
                elif self.config.distance_metric == "euclidean":
                    self.index = self.faiss.IndexHNSWFlat(dimension, self.config.hnsw_m, self.faiss.METRIC_L2)
                    self.index.hnsw.efConstruction = self.config.hnsw_ef_construction
                    self.index.hnsw.efSearch = self.config.hnsw_ef_search
                else:
                    self.index = self.faiss.IndexHNSWFlat(dimension, self.config.hnsw_m)
            
            else:
                # Default to flat index
                self.index = self.faiss.IndexFlatIP(dimension)
            
            # Reset mappings
            self.id_map = {}
            self.metadata_map = {}
            self.content_map = {}
            self.next_id = 0
            
            logger.info(f"Created FAISS index with dimension {dimension}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create FAISS index: {e}")
            return False
    
    async def delete_collection(self) -> bool:
        """Delete the collection"""
        try:
            self.index = None
            self.id_map = {}
            self.metadata_map = {}
            self.content_map = {}
            self.next_id = 0
            
            # Delete persisted files
            if self.config.persist_directory:
                index_file = os.path.join(self.config.persist_directory, f"{self.config.collection_name}.index")
                metadata_file = os.path.join(self.config.persist_directory, f"{self.config.collection_name}_metadata.pkl")
                
                for file_path in [index_file, metadata_file]:
                    if os.path.exists(file_path):
                        os.remove(file_path)
            
            logger.info("Deleted FAISS collection")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete FAISS collection: {e}")
            return False
    
    async def add_vectors(
        self, 
        ids: List[str], 
        vectors: List[List[float]], 
        metadatas: List[Dict[str, Any]],
        contents: List[str]
    ) -> bool:
        """Add vectors to the index"""
        try:
            if not self.index:
                logger.error("Index not initialized")
                return False
            
            # Convert to numpy array
            vectors_np = np.array(vectors, dtype=np.float32)
            
            # Normalize vectors if using cosine similarity
            if self.config.distance_metric == "cosine":
                norms = np.linalg.norm(vectors_np, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1, norms)  # Avoid division by zero
                vectors_np = vectors_np / norms
            
            # Add vectors to index
            start_idx = self.index.ntotal
            self.index.add(vectors_np)
            
            # Update mappings
            for i, doc_id in enumerate(ids):
                internal_id = start_idx + i
                self.id_map[internal_id] = doc_id
                self.metadata_map[doc_id] = metadatas[i]
                self.content_map[doc_id] = contents[i]
            
            self.next_id = self.index.ntotal
            
            # Persist if configured
            if self.config.persist_directory:
                self._save_index()
            
            logger.info(f"Added {len(ids)} vectors to FAISS index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add vectors to FAISS: {e}")
            return False
    
    async def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors by IDs (FAISS doesn't support deletion, so we rebuild)"""
        try:
            if not self.index:
                logger.error("Index not initialized")
                return False
            
            # Remove from mappings
            internal_ids_to_remove = []
            for internal_id, doc_id in self.id_map.items():
                if doc_id in ids:
                    internal_ids_to_remove.append(internal_id)
            
            for internal_id in internal_ids_to_remove:
                doc_id = self.id_map[internal_id]
                del self.id_map[internal_id]
                if doc_id in self.metadata_map:
                    del self.metadata_map[doc_id]
                if doc_id in self.content_map:
                    del self.content_map[doc_id]
            
            # For FAISS, we need to rebuild the index without deleted vectors
            # This is expensive but necessary since FAISS doesn't support deletion
            if internal_ids_to_remove:
                self._rebuild_index()
            
            logger.info(f"Deleted {len(ids)} vectors from FAISS index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete vectors from FAISS: {e}")
            return False
    
    async def search(
        self, 
        query_vector: List[float], 
        limit: int = 5,
        filter_dict: Dict[str, Any] = None
    ) -> List[SearchResult]:
        """Search for similar vectors"""
        try:
            if not self.index or self.index.ntotal == 0:
                return []
            
            # Convert query to numpy array
            query_np = np.array([query_vector], dtype=np.float32)
            
            # Normalize if using cosine similarity
            if self.config.distance_metric == "cosine":
                norm = np.linalg.norm(query_np)
                if norm > 0:
                    query_np = query_np / norm
            
            # Search the index
            distances, indices = self.index.search(query_np, min(limit * 2, self.index.ntotal))
            
            # Convert results
            search_results = []
            for i, (distance, internal_id) in enumerate(zip(distances[0], indices[0])):
                if internal_id == -1:  # Invalid result
                    continue
                
                doc_id = self.id_map.get(internal_id)
                if not doc_id:
                    continue
                
                # Apply filters if provided
                if filter_dict:
                    metadata = self.metadata_map.get(doc_id, {})
                    if not self._matches_filter(metadata, filter_dict):
                        continue
                
                # Convert distance to score
                if self.config.distance_metric == "cosine":
                    score = distance  # Inner product for cosine (higher is better)
                else:
                    score = 1.0 / (1.0 + distance)  # Convert L2 distance to similarity
                
                result = SearchResult(
                    id=doc_id,
                    content=self.content_map.get(doc_id, ""),
                    metadata=self.metadata_map.get(doc_id, {}),
                    score=score,
                    distance=distance
                )
                search_results.append(result)
                
                if len(search_results) >= limit:
                    break
            
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to search FAISS index: {e}")
            return []
    
    async def get_by_ids(self, ids: List[str]) -> List[SearchResult]:
        """Get vectors by their IDs"""
        try:
            search_results = []
            for doc_id in ids:
                if doc_id in self.metadata_map:
                    result = SearchResult(
                        id=doc_id,
                        content=self.content_map.get(doc_id, ""),
                        metadata=self.metadata_map.get(doc_id, {}),
                        score=1.0,
                        distance=0.0
                    )
                    search_results.append(result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Failed to get vectors by IDs from FAISS: {e}")
            return []
    
    async def get_all_ids(self, filter_dict: Dict[str, Any] = None) -> List[str]:
        """Get all document IDs in the collection"""
        try:
            if filter_dict:
                # Apply filter
                filtered_ids = []
                for doc_id, metadata in self.metadata_map.items():
                    if self._matches_filter(metadata, filter_dict):
                        filtered_ids.append(doc_id)
                return filtered_ids
            else:
                return list(self.metadata_map.keys())
            
        except Exception as e:
            logger.error(f"Failed to get all IDs from FAISS: {e}")
            return []
    
    async def count(self, filter_dict: Dict[str, Any] = None) -> int:
        """Count documents in the collection"""
        ids = await self.get_all_ids(filter_dict)
        return len(ids)
    
    def _matches_filter(self, metadata: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        """Check if metadata matches filter criteria"""
        for key, value in filter_dict.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True
    
    def _rebuild_index(self):
        """Rebuild the index without deleted vectors"""
        if not self.index or self.index.ntotal == 0:
            return
        
        # Get all remaining vectors
        remaining_vectors = []
        remaining_ids = []
        remaining_metadatas = []
        remaining_contents = []
        
        for internal_id, doc_id in self.id_map.items():
            if doc_id in self.metadata_map:
                # Get vector from index
                vector = self.index.reconstruct(internal_id)
                remaining_vectors.append(vector)
                remaining_ids.append(doc_id)
                remaining_metadatas.append(self.metadata_map[doc_id])
                remaining_contents.append(self.content_map[doc_id])
        
        # Recreate index
        if remaining_vectors:
            self.create_collection(self.dimension)
            self.add_vectors(remaining_ids, remaining_vectors, remaining_metadatas, remaining_contents)
    
    def _save_index(self):
        """Save the index and metadata to disk"""
        if not self.config.persist_directory:
            return
        
        os.makedirs(self.config.persist_directory, exist_ok=True)
        
        # Save FAISS index
        index_file = os.path.join(self.config.persist_directory, f"{self.config.collection_name}.index")
        self.faiss.write_index(self.index, index_file)
        
        # Save metadata
        metadata_file = os.path.join(self.config.persist_directory, f"{self.config.collection_name}_metadata.pkl")
        metadata = {
            "id_map": self.id_map,
            "metadata_map": self.metadata_map,
            "content_map": self.content_map,
            "next_id": self.next_id,
            "dimension": self.dimension
        }
        with open(metadata_file, "wb") as f:
            pickle.dump(metadata, f)
    
    def _load_index(self):
        """Load the index and metadata from disk"""
        if not self.config.persist_directory:
            return
        
        index_file = os.path.join(self.config.persist_directory, f"{self.config.collection_name}.index")
        metadata_file = os.path.join(self.config.persist_directory, f"{self.config.collection_name}_metadata.pkl")
        
        if os.path.exists(index_file) and os.path.exists(metadata_file):
            try:
                # Load FAISS index
                self.index = self.faiss.read_index(index_file)
                
                # Load metadata
                with open(metadata_file, "rb") as f:
                    metadata = pickle.load(f)
                
                self.id_map = metadata["id_map"]
                self.metadata_map = metadata["metadata_map"]
                self.content_map = metadata["content_map"]
                self.next_id = metadata["next_id"]
                self.dimension = metadata["dimension"]
                
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")
                
            except Exception as e:
                logger.error(f"Failed to load FAISS index: {e}")
                # Reset on load failure
                self.index = None
                self.id_map = {}
                self.metadata_map = {}
                self.content_map = {}
                self.next_id = 0
