"""
ThreadScopedRAG Node - Workflow node for per-chat RAG operations

This node allows workflows to:
- Add messages to chat history for RAG
- Retrieve relevant context from chat history
- Configure chunking and embedding settings per workflow
"""

import logging
from typing import Dict, Any

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.agents.rag import ThreadScopedRAG

logger = logging.getLogger(__name__)


class ThreadRAGNode(BaseNode):
    """
    Workflow node for per-chat RAG operations.

    Configuration options:
    - action: "add" or "retrieve" (required)
    - chat_id: Chat/thread identifier (required, can use {{thread_id}} template)
    - query: Search query (required for retrieve action)
    - message: Message content to add (required for add action)
    - message_id: Unique message identifier (optional, auto-generated if not provided)
    - top_k: Number of results to return (default: 5, for retrieve action)
    - chunk_long_messages: Whether to chunk long messages (default: true, for add action)
    - filename: Optional filename for file content (for add action)
    """

    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Process a ThreadScopedRAG node operation.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with operation results
        """
        action = config.get("action", "retrieve")
        chat_id = self.get_state().get_thread_id()

        # Get ThreadScopedRAG instance from injector
        try:
            from app.dependencies.injector import injector

            thread_rag = injector.get(ThreadScopedRAG)
        except Exception as e:
            error_msg = f"Failed to get ThreadScopedRAG instance: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}

        try:
            if action == "add":
                return await self._add_message(thread_rag, chat_id, config)
            elif action == "retrieve":
                return await self._retrieve(thread_rag, chat_id, config)
            elif action == "add_file":
                return await self._add_file(thread_rag, chat_id, config)
            else:
                error_msg = f"Unknown action: {action}. Supported actions: add, retrieve, add_file"
                logger.error(error_msg)
                return {"error": error_msg}

        except Exception as e:
            error_msg = f"Error processing ThreadScopedRAG node: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    async def _add_message(
        self, thread_rag: ThreadScopedRAG, chat_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a message to chat history"""
        message = config.get("message")
        if not message:
            return {"error": "message is required for add action"}

        message_id = config.get("message_id")
        if not message_id:
            import uuid

            message_id = str(uuid.uuid4())

        chunk_long_messages = config.get("chunk_long_messages", True)
        filename = config.get("filename")

        if chunk_long_messages or len(message) > 1000:
            await thread_rag.add_long_message(
                chat_id=chat_id,
                message=message,
                message_id=message_id,
                chunk_long_messages=chunk_long_messages,
                filename=filename,
            )
        else:
            await thread_rag.add_message(
                chat_id=chat_id, message=message, message_id=message_id
            )

        return {
            "success": True,
            "action": "add",
            "chat_id": chat_id,
            "message_id": message_id,
        }

    async def _retrieve(
        self, thread_rag: ThreadScopedRAG, chat_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve relevant context from chat history"""
        query = config.get("query")
        if not query:
            return {"error": "query is required for retrieve action"}

        top_k = config.get("top_k", 5)

        results = await thread_rag.retrieve(chat_id=chat_id, query=query, top_k=top_k)

        return {
            "success": True,
            "action": "retrieve",
            "chat_id": chat_id,
            "query": query,
            "results": results,
            "count": len(results),
        }

    async def _add_file(
        self, thread_rag: ThreadScopedRAG, chat_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add file content to chat history"""
        file_content = config.get("file_content")
        file_name = config.get("file_name", "unknown")
        file_id = config.get("file_id")

        if not file_content:
            return {"error": "file_content is required for add_file action"}

        await thread_rag.add_file_content(
            chat_id=chat_id,
            file_content=file_content,
            file_name=file_name,
            file_id=file_id,
        )

        return {
            "success": True,
            "action": "add_file",
            "chat_id": chat_id,
            "file_name": file_name,
            "file_id": file_id,
        }
