"""
ThreadScopedRAG: Per-Chat Retrieval-Augmented Generation (RAG) using AgentRAGService

- Each chat (thread_id/conversation_id) gets its own AgentRAGService instance.
- When a message is added to a chat, it is stored via AgentRAGService (with automatic chunking and embedding).
- To answer a user query, retrieve the most relevant previous messages from the same chat only.
- Use ThreadScopedRAG.add_message(chat_id, message, message_id) to add messages.
- Use ThreadScopedRAG.retrieve(chat_id, query, top_k) to get relevant context for RAG.
- Tenant-scoped singleton instance available via dependency injection.

Set the OPENAI_API_KEY environment variable before use.
"""

import asyncio
import logging
from typing import List, Dict, Optional
import uuid

from injector import inject

from app.core.config.settings import settings
from app.modules.data.service import AgentRAGService
from app.modules.data.config import AgentRAGConfig
from app.modules.data.providers import SearchResult
from app.modules.data.providers.vector import VectorConfig
from app.modules.data.providers.vector.chunking import ChunkConfig
from app.modules.data.providers.vector.embedding import EmbeddingConfig
from app.modules.data.providers.vector.db import VectorDBConfig

logger = logging.getLogger(__name__)

# Default configuration matching original behavior
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "text-embedding-ada-002"


def _create_default_config(chat_id: str) -> AgentRAGConfig:
    """
    Create a default AgentRAGConfig for a chat with OpenAI embeddings and ChromaDB.

    Args:
        chat_id: Chat identifier (used as knowledge_base_id)

    Returns:
        AgentRAGConfig with vector provider enabled
    """
    # Configure chunking (matching original MAX_CHUNK_SIZE and CHUNK_OVERLAP)
    chunk_config = ChunkConfig(
        type="recursive",
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
        keep_separator=True,
        strip_whitespace=True,
    )

    # Configure OpenAI embeddings (matching original EMBEDDING_MODEL)
    embedding_config = EmbeddingConfig(
        type="openai",
        model_name=EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
        batch_size=32,
        normalize_embeddings=True,
        device="cpu",
    )

    # Configure ChromaDB vector database
    vector_db_config = VectorDBConfig(type="chroma", collection_name=f"chat_{chat_id}")

    # Create vector config
    vector_config = VectorConfig(
        enabled=True,
        chunking=chunk_config,
        embedding=embedding_config,
        vector_db=vector_db_config,
    )

    # Create AgentRAGConfig
    return AgentRAGConfig(knowledge_base_id=chat_id, vector_config=vector_config)


@inject
class ThreadScopedRAG:
    """
    Manages an AgentRAGService instance for each chat (by chat_id/thread_id).
    Allows adding messages and retrieving relevant context for RAG.
    Tenant-scoped singleton - each tenant gets their own instance.
    """

    def __init__(self):
        self._services: Dict[str, AgentRAGService] = {}
        self._initialization_locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        logger.info("ThreadScopedRAG initialized (tenant-scoped)")

    async def _get_service(self, chat_id: str) -> Optional[AgentRAGService]:
        """
        Get or create an AgentRAGService for a chat.

        Args:
            chat_id: Chat identifier

        Returns:
            AgentRAGService instance or None if creation fails
        """
        # Return existing service if available and initialized
        if chat_id in self._services:
            service = self._services[chat_id]
            if service.is_initialized():
                return service
            else:
                # Remove failed service
                logger.warning(f"Removing uninitialized service for chat {chat_id}")
                if chat_id in self._services:
                    del self._services[chat_id]

        # Ensure we have a lock for this chat
        if chat_id not in self._initialization_locks:
            async with self._lock:
                if chat_id not in self._initialization_locks:
                    self._initialization_locks[chat_id] = asyncio.Lock()

        # Use lock to prevent concurrent initialization
        async with self._initialization_locks[chat_id]:
            # Double-check pattern - service might have been created while waiting
            if chat_id in self._services and self._services[chat_id].is_initialized():
                return self._services[chat_id]

            try:
                # Create service with default config
                config = _create_default_config(chat_id)
                service = AgentRAGService(config)

                # Initialize service
                success = await service.initialize()
                if not success:
                    logger.error(
                        f"Failed to initialize AgentRAGService for chat {chat_id}"
                    )
                    return None

                # Cache the service
                self._services[chat_id] = service
                logger.info(f"Created and cached AgentRAGService for chat {chat_id}")
                return service

            except Exception as e:
                logger.error(f"Error creating AgentRAGService for chat {chat_id}: {e}")
                return None

    async def add_message(self, chat_id: str, message: str, message_id: str):
        """
        Add a message to the chat's vector store.

        Args:
            chat_id: Chat identifier
            message: Message content
            message_id: Unique message identifier
        """
        service = await self._get_service(chat_id)
        if not service:
            logger.error(f"Could not get service for chat {chat_id}")
            return

        try:
            metadata = {
                "message_id": message_id,
                "chat_id": chat_id,
                "is_chunked": False,
            }
            result = await service.add_document(
                message_id, message, metadata, legra_finalize=False
            )
            if not any(result.values()):
                logger.warning(f"Failed to add message {message_id} to chat {chat_id}")
        except Exception as e:
            logger.error(f"Error adding message {message_id} to chat {chat_id}: {e}")

    async def add_long_message(
        self,
        chat_id: str,
        message: str,
        message_id: str,
        chunk_long_messages: bool = True,
        filename: Optional[str] = None,
    ):
        """
        Add a message to the chat's vector store.
        If chunk_long_messages is True, long messages will be split into chunks by AgentRAGService.

        Args:
            chat_id: Chat identifier
            message: Message content
            message_id: Unique message identifier
            chunk_long_messages: Whether to chunk long messages (handled by AgentRAGService)
            filename: Optional filename for file content
        """
        service = await self._get_service(chat_id)
        if not service:
            logger.error(f"Could not get service for chat {chat_id}")
            return

        try:
            metadata = {
                "message_id": message_id,
                "chat_id": chat_id,
                "is_chunked": chunk_long_messages,
                "filename": filename,
            }
            result = await service.add_document(
                message_id, message, metadata, legra_finalize=False
            )
            if not any(result.values()):
                logger.warning(f"Failed to add message {message_id} to chat {chat_id}")
        except Exception as e:
            logger.error(
                f"Error adding long message {message_id} to chat {chat_id}: {e}"
            )

    async def add_file_content(
        self,
        chat_id: str,
        file_content: str,
        file_name: str,
        file_id: Optional[str] = None,
    ):
        """
        Convenience method to add file content with appropriate chunking.

        Args:
            chat_id: Chat identifier
            file_content: File content text
            file_name: Name of the file
            file_id: Optional file identifier (generated if not provided)
        """
        if file_id is None:
            file_id = str(uuid.uuid4())

        # Add file metadata as context
        file_context = f"File: {file_name}\n\n{file_content}"

        await self.add_long_message(
            chat_id=chat_id,
            message=file_context,
            message_id=f"file_{file_id}",
            chunk_long_messages=True,
            filename=file_name,
        )

    async def retrieve(self, chat_id: str, query: str, top_k: int = 5) -> List[Dict]:
        """
        Retrieve relevant context with metadata about chunking.
        Returns list of dicts with 'content' and 'metadata' keys (backward compatible format).

        Args:
            chat_id: Chat identifier
            query: Search query
            top_k: Number of results to return

        Returns:
            List of dicts with 'content' and 'metadata' keys
        """
        service = await self._get_service(chat_id)
        if not service:
            logger.error(f"Could not get service for chat {chat_id}")
            return []

        try:
            # Search using AgentRAGService
            search_results: List[SearchResult] = await service.search(
                query, limit=top_k
            )

            if not search_results:
                return []

            # Convert SearchResult to backward-compatible format
            retrieved_docs = []
            for result in search_results:
                # Extract metadata from SearchResult
                metadata = result.metadata.copy() if result.metadata else {}

                # Ensure backward compatibility with original format
                retrieved_docs.append({"content": result.content, "metadata": metadata})

            return retrieved_docs

        except Exception as e:
            logger.error(f"Error retrieving from chat {chat_id}: {e}")
            return []
