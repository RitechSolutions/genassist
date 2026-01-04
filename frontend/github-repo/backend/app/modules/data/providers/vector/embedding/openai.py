"""
OpenAI embedding provider implementation
"""

import logging
from typing import List


from .base import BaseEmbedder, EmbeddingConfig

logger = logging.getLogger(__name__)


class OpenAIEmbedder(BaseEmbedder):
    """OpenAI embedding provider"""
    
    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.client = None
        # Dimension mapping for OpenAI models
        self._model_dimensions = {
            "text-embedding-ada-002": 1536,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
        }
    
    async def get_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        if self._dimension is None:
            self._dimension = self._model_dimensions.get(self.config.model_name, 1536)
        return self._dimension
    
    async def initialize(self) -> bool:
        """Initialize the OpenAI client"""
        try:
            from langchain_openai import OpenAIEmbeddings
            
            if not self.config.api_key:
                raise ValueError("OpenAI API key is required")
            
            client_kwargs = {
                "api_key": self.config.api_key
            }
            
            if self.config.base_url:
                client_kwargs["base_url"] = self.config.base_url
            
            self.client = OpenAIEmbeddings(
                model=self.config.model_name,
                openai_api_key=self.config.api_key,
                openai_api_base=self.config.base_url
            )
            
            logger.info(f"Initialized OpenAI embeddings with model: {self.config.model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI embeddings: {e}")
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
        
        if not self.client:
            if not await self.initialize():
                raise RuntimeError("Failed to initialize OpenAI client")
        
        try:
            # Use LangChain's embed_documents method for batch processing
            embeddings = await self.client.aembed_documents(texts)
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
        if not self.client:
            if not await self.initialize():
                raise RuntimeError("Failed to initialize OpenAI client")
        
        try:
            # Use LangChain's embed_query method
            embedding = await self.client.aembed_query(query)
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []
