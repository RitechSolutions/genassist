"""
AWS Bedrock embedding provider implementation
"""

import logging
from typing import List

from .base import BaseEmbedder, EmbeddingConfig

logger = logging.getLogger(__name__)


class BedrockEmbedder(BaseEmbedder):
    """AWS Bedrock embedding provider using LangChain"""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.client = None
        # Dimension mapping for Bedrock models
        self._model_dimensions = {
            "amazon.titan-embed-text-v2:0": 1024,
            "amazon.titan-embed-text-v1": 1536,
            "cohere.embed-english-v3": 1024,
            "cohere.embed-multilingual-v3": 1024,
        }

    async def get_dimension(self) -> int:
        """Get the dimension of the embeddings"""
        if self._dimension is None:
            model_id = self.config.model_id or "amazon.titan-embed-text-v2:0"
            self._dimension = self._model_dimensions.get(model_id, 1024)
        return self._dimension

    async def initialize(self) -> bool:
        """Initialize the Bedrock client"""
        try:
            from langchain_aws import BedrockEmbeddings

            # Use model_id from config or default
            model_id = self.config.model_id or "amazon.titan-embed-text-v2:0"
            region_name = self.config.region_name or "ca-central-1"

            # Initialize Bedrock embeddings
            # Credentials are automatically loaded from boto3's credential chain:
            # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
            # 2. AWS credentials file (~/.aws/credentials)
            # 3. IAM instance profile (EC2/ECS)
            # 4. IAM role (Lambda/ECS with task role)
            self.client = BedrockEmbeddings(
                model_id=model_id,
                region_name=region_name
            )

            logger.info(
                f"Initialized Bedrock embeddings with model: {model_id} in region: {region_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Bedrock embeddings: {e}")
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
                raise RuntimeError("Failed to initialize Bedrock client")

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
                raise RuntimeError("Failed to initialize Bedrock client")

        try:
            # Use LangChain's embed_query method
            embedding = await self.client.aembed_query(query)
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []