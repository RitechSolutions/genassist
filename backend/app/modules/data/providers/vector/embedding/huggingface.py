"""
HuggingFace embedding provider implementation
"""

import logging
from typing import List

from langchain_huggingface import HuggingFaceEmbeddings

from .base import BaseEmbedder, EmbeddingConfig

logger = logging.getLogger(__name__)


class HuggingFaceEmbedder(BaseEmbedder):
    """HuggingFace embedding provider using LangChain"""
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.embeddings = None
    
    async def get_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        if self._dimension is None:
            # Initialize if not done already
            if not self.embeddings:
                await self.initialize()
            
            # Get dimension by embedding a test text
            try:
                test_embedding = await self.embeddings.aembed_query("test")
                self._dimension = len(test_embedding)
            except Exception as e:
                logger.error(f"Failed to get embedding dimension: {e}")
                # Common dimensions for popular models
                dimension_map = {
                    "all-MiniLM-L6-v2": 384,
                    "all-mpnet-base-v2": 768,
                    "sentence-transformers/all-MiniLM-L6-v2": 384,
                    "sentence-transformers/all-mpnet-base-v2": 768,
                }
                self._dimension = dimension_map.get(self.config.model_name, 768)
        
        return self._dimension
    
    async def initialize(self) -> bool:
        """Initialize the HuggingFace embedding model"""
        try:
            model_kwargs = {
                'device': self.config.device
            }
            
            encode_kwargs = {
                'normalize_embeddings': self.config.normalize_embeddings,
                'batch_size': self.config.batch_size
            }
            
            if self.config.max_length:
                encode_kwargs['max_length'] = self.config.max_length
            
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.config.model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs
            )
            
            logger.info(f"Initialized HuggingFace embeddings with model: {self.config.model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize HuggingFace embeddings: {e}")
            return False
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        if not self.embeddings:
            if not await self.initialize():
                raise RuntimeError("Failed to initialize embeddings model")
        
        try:
            # Use LangChain's embed_documents method for batch processing
            embeddings = await self.embeddings.aembed_documents(texts)
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return []
    
    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query
        
        Args:
            query: Query text to embed
            
        Returns:
            Embedding vector
        """
        if not self.embeddings:
            if not await self.initialize():
                raise RuntimeError("Failed to initialize embeddings model")
        
        try:
            # Use LangChain's embed_query method which may have different preprocessing
            embedding = await self.embeddings.aembed_query(query)
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []
