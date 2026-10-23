"""
AWS Bedrock embedding provider implementation
"""

import asyncio
import logging
from contextlib import contextmanager
from typing import List

from app.core.config.settings import settings
from .base import BaseEmbedder, EmbeddingConfig

logger = logging.getLogger(__name__)


def _close_connection_after_call(request, **kwargs):
    """Close each Bedrock connection after its answer so a connection dropped while idle is never reused"""
    request.headers["Connection"] = "close"


class BedrockEmbedder(BaseEmbedder):
    """AWS Bedrock embedding provider using LangChain"""

    def __init__(self, config: EmbeddingConfig):
        super().__init__(config)
        self.client = None
        self._batch_client = None
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

    def _build_client(self, close_after_each_call: bool):
        """Build a Bedrock client; without close_after_each_call it reuses its connections"""
        from botocore.config import Config
        from langchain_aws import BedrockEmbeddings

        # Credentials come from boto3's default chain (environment, credentials file, instance or task role)
        client = BedrockEmbeddings(
            model_id=self.config.model_id or "amazon.titan-embed-text-v2:0",
            region_name=self.config.region_name or "ca-central-1",
            config=Config(**self._client_timeouts()),
        )
        if close_after_each_call:
            client.client.meta.events.register("before-send.bedrock-runtime", _close_connection_after_call)
        return client

    def _client_timeouts(self) -> dict:
        """Knowledge-base timeouts when set; otherwise the embedding timeout to connect and the AWS default to read"""
        connect_timeout = self.config.connect_timeout
        if connect_timeout is None:
            connect_timeout = settings.BEDROCK_TIMEOUT_QUERY_EMBEDDING_SECONDS
        timeouts = {"connect_timeout": connect_timeout}
        if self.config.read_timeout is not None:
            timeouts["read_timeout"] = self.config.read_timeout
        return timeouts

    async def initialize(self) -> bool:
        """Initialize the Bedrock clients; the batch client is built once and kept on re-initialization"""
        try:
            client = self._build_client(close_after_each_call=True)
            batch_client = self._batch_client
            if batch_client is None:
                batch_client = self._build_client(close_after_each_call=False)
            self.client, self._batch_client = client, batch_client
            logger.info(
                f"Initialized Bedrock embeddings with model: {self.client.model_id} in region: {self.client.region_name}")
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

        if self._batch_client is None:
            if not await self.initialize():
                raise RuntimeError("Failed to initialize Bedrock client")

        try:
            with self._batch_connections() as client:
                # Use LangChain's embed_documents method for batch processing
                embeddings = await client.aembed_documents(texts)
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return []

    @contextmanager
    def _batch_connections(self):
        """Batch client that starts with no pooled connections and drops them again when the batch ends"""
        batch_client = self._batch_client
        batch_client.client.close()
        try:
            yield batch_client
        finally:
            batch_client.client.close()

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a query with timeout and retry mechanism

        Args:
            query: Query text to embed

        Returns:
            Embedding vector
        """
        if not self.client:
            if not await self.initialize():
                raise RuntimeError("Failed to initialize Bedrock client")

        max_retries = settings.BEDROCK_MAX_RETRY_QUERY_EMBEDDING
        timeout_seconds = settings.BEDROCK_TIMEOUT_QUERY_EMBEDDING_SECONDS

        for attempt in range(max_retries):
            try:
                embedding = await asyncio.wait_for(
                    self.client.aembed_query(query),
                    timeout=timeout_seconds
                )
                return embedding

            except asyncio.TimeoutError:
                logger.warning(
                    f"Bedrock embed_query timed out after {timeout_seconds}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                
                # Reinitialize client after timeout to ensure clean connection
                # This helps prevent hanging connections from accumulating
                if attempt < max_retries - 1:
                    logger.info("Reinitializing Bedrock client after timeout")
                    self.client = None
                    if not await self.initialize():
                        logger.error("Failed to reinitialize Bedrock client")
                        return []
                else:
                    logger.error(
                        f"Failed to generate query embedding after {max_retries} attempts due to timeout"
                    )
                    return []

            except Exception as e:
                logger.error(f"Failed to generate query embedding: {e}")
                return []

        return []
