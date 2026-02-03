"""
AWS Bedrock embedding provider implementation
"""

import asyncio
import logging
from typing import List

from .base import BaseEmbedder, EmbeddingConfig

logger = logging.getLogger(__name__)

# Default timeouts (seconds) so requests don't hang; Bedrock can be slow or stall
DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 120
# Smaller batches = more parallel API calls; Bedrock is one request per text
BEDROCK_PARALLEL_BATCH_SIZE = 8


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
            import boto3
            from botocore.config import Config
            from langchain_aws import BedrockEmbeddings

            # Use model_id from config or default
            model_id = self.config.model_id or "amazon.titan-embed-text-v2:0"
            region_name = self.config.region_name or "ca-central-1"

            connect_timeout = (
                self.config.connect_timeout
                if self.config.connect_timeout is not None
                else DEFAULT_CONNECT_TIMEOUT
            )
            read_timeout = (
                self.config.read_timeout
                if self.config.read_timeout is not None
                else DEFAULT_READ_TIMEOUT
            )
            boto_config = Config(
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
            )
            bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=region_name,
                config=boto_config,
            )

            # Credentials come from boto3's chain (env, ~/.aws/credentials, IAM)
            self.client = BedrockEmbeddings(
                model_id=model_id,
                region_name=region_name,
                client=bedrock_client,
            )

            logger.info(
                "Initialized Bedrock embeddings with model: %s in region: %s "
                "(connect_timeout=%s, read_timeout=%s)",
                model_id,
                region_name,
                connect_timeout,
                read_timeout,
            )
            return True

        except Exception as e:
            logger.error("Failed to initialize Bedrock embeddings: %s", e)
            return False

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Processes texts in batches and runs batches concurrently so that
        multiple Bedrock API calls proceed in parallel, reducing total time
        (Bedrock is one text per request; LangChain uses sync boto3).
        """
        if not texts:
            return []

        if not self.client:
            if not await self.initialize():
                raise RuntimeError("Failed to initialize Bedrock client")

        try:
            # Use small batches so we run many batches in parallel (Bedrock = 1 call per text)
            batch_size = min(
                BEDROCK_PARALLEL_BATCH_SIZE,
                max(1, self.config.batch_size),
            )
            batches = [
                texts[i : i + batch_size]
                for i in range(0, len(texts), batch_size)
            ]
            if len(batches) == 1:
                # Single batch: run sync embed_documents in executor to avoid blocking
                loop = asyncio.get_event_loop()
                embeddings = await loop.run_in_executor(
                    None,
                    lambda b=batches[0]: self.client.embed_documents(b),
                )
                return embeddings
            # Multiple batches: run each batch in executor and gather
            loop = asyncio.get_event_loop()

            def embed_batch(batch: List[str]) -> List[List[float]]:
                return self.client.embed_documents(batch)

            batch_results = await asyncio.gather(
                *[
                    loop.run_in_executor(None, embed_batch, batch)
                    for batch in batches
                ]
            )
            # Preserve order
            result: List[List[float]] = []
            for batch_embeddings in batch_results:
                result.extend(batch_embeddings)
            return result
        except Exception as e:
            logger.error("Failed to generate embeddings: %s", e)
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
            # Run in executor so sync boto3 call doesn't block the event loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.client.embed_query,
                query,
            )
        except Exception as e:
            logger.error("Failed to generate query embedding: %s", e)
            return []