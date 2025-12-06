from typing import Dict, Any, List, Union
import logging
from datetime import datetime
import json
from redis.asyncio import Redis
from app.cache.redis_connection_manager import RedisConnectionManager
from app.core.config.settings import settings


logger = logging.getLogger(__name__)


class Message:
    """Message class"""

    def __init__(self, role: str, content: Any, message_type: str = "text"):
        """Initialize the message"""
        self.role: str = role
        self.content: Any = content
        self.message_type: str = message_type
        self.timestamp: str = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the message to a dictionary"""
        return {
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type,
            "timestamp": self.timestamp,
        }


class BaseConversationMemory:
    """Base class for conversation memory implementations"""

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.messages: List[Message] = []
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now().isoformat()
        self.last_updated = self.created_at
        self.executions_count = 0

    async def add_message(self, message: Message) -> None:
        """Add a message to the conversation"""
        raise NotImplementedError

    async def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation"""
        raise NotImplementedError

    async def add_assistant_message(self, content: Any) -> None:
        """Add an assistant message to the conversation"""
        raise NotImplementedError

    async def get_messages(
        self, max_messages: int = 10, roles: List[str] | None = None
    ) -> List[Union[Message, dict[str, Any]]]:
        """Get messages from the conversation, optionally filtered by role"""
        raise NotImplementedError

    async def clear(self) -> None:
        """Clear the conversation"""
        raise NotImplementedError

    async def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata for the conversation"""
        raise NotImplementedError

    async def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata for the conversation"""
        raise NotImplementedError

    async def get_chat_history(
        self, as_string: bool = False, max_messages: int = 10
    ) -> Union[List[Message], str]:
        """Get the chat history in a format suitable for LLM context"""
        raise NotImplementedError


class InMemoryConversationMemory(BaseConversationMemory):
    """In-memory implementation of conversation memory"""

    async def add_message(self, message: Message) -> None:
        """Add a message to the conversation"""
        message = Message(message.role, message.content, message.message_type)
        self.messages.append(message)
        self.last_updated = message.timestamp

    async def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation"""
        await self.add_message(Message("user", content))

    async def add_assistant_message(self, content: Any) -> None:
        """Add an assistant message to the conversation"""
        await self.add_message(Message("assistant", content))

    async def get_messages(
        self, max_messages: int = 10, roles: List[str] | None = None
    ) -> List[Union[Message, dict[str, Any]]]:
        """Get messages from the conversation, optionally filtered by role"""
        filtered = self.messages
        if roles:
            filtered = [m for m in filtered if m.role in roles]
        if max_messages:
            filtered = filtered[-max_messages:]
        return [messages.to_dict() for messages in filtered]

    async def clear(self) -> None:
        """Clear the conversation"""
        self.messages = []
        self.last_updated = datetime.now().isoformat()
        self.executions_count = 0

    async def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata for the conversation"""
        self.metadata[key] = value

    async def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata for the conversation"""
        return self.metadata.get(key, default)

    async def get_chat_history(
        self, as_string: bool = False, max_messages: int = 10
    ) -> Union[List[Message], str]:
        """Get the chat history in a format suitable for LLM context"""
        if as_string:
            history_parts = []
            for message in self.messages[-max_messages:]:
                prefix = f"{message.role.capitalize()}: "
                content = message.content
                history_parts.append(f"{prefix}{content}")
            return "\n".join(history_parts)

        return self.messages[-max_messages:]


class RedisConversationMemory(BaseConversationMemory):
    """Redis-based implementation of conversation memory with tenant isolation"""

    def __init__(self, thread_id: str):
        super().__init__(thread_id)
        self.redis_client: Redis | None = None
        # Prefix keys with tenant context for isolation
        tenant_prefix = self._get_tenant_prefix()
        self._message_key = f"{tenant_prefix}:conversation:{self.thread_id}:messages"
        self._metadata_key = f"{tenant_prefix}:conversation:{self.thread_id}:metadata"
        self._conversation_key = f"{tenant_prefix}:conversation:{self.thread_id}:info"
        self.initialized = False

    def _get_tenant_prefix(self) -> str:
        """Get tenant-aware key prefix"""
        from app.core.tenant_scope import get_tenant_context

        tenant_id = get_tenant_context()
        if tenant_id:
            return f"tenant:{tenant_id}:"
        return ""  # Fallback for non-multi-tenant mode

    async def _get_redis(self) -> Redis:
        """Get Redis client, initializing if needed"""
        if self.redis_client is None:
            from app.dependencies.injector import injector
            manager = injector.get(RedisConnectionManager)
            self.redis_client = await manager.get_redis()
        return self.redis_client

    async def _initialize_conversation(self) -> None:
        """Initialize conversation data in Redis if it doesn't exist"""
        redis = await self._get_redis()

        # Check if conversation exists
        if self.initialized:
            return
        exists = await redis.exists(self._conversation_key)
        if not exists:
            # Initialize conversation metadata
            conversation_data = {
                "thread_id": self.thread_id,
                "created_at": self.created_at,
                "last_updated": self.last_updated,
                "executions_count": self.executions_count,
            }
            # type: ignore
            await redis.hset(self._conversation_key, mapping=conversation_data)
            # type: ignore
            await redis.expire(self._conversation_key, 86400 * 30)
        self.initialized = True

    async def add_message(self, message: Message) -> None:
        """Add a message to the conversation in Redis"""
        try:
            await self._initialize_conversation()
            redis = await self._get_redis()

            # Create message data
            message_data = message.to_dict()
            message_json = json.dumps(message_data)

            # Add message to Redis list
            await redis.lpush(self._message_key, message_json)  # type: ignore

            # Update last_updated timestamp
            self.last_updated = message.timestamp
            # type: ignore
            await redis.hset(self._conversation_key, "last_updated", self.last_updated)

            # Set TTL for message list (30 days)
            await redis.expire(self._message_key, 86400 * 30)  # type: ignore

            logger.debug(f"Added message to Redis for thread {self.thread_id}")

        except Exception as e:
            logger.error(
                f"Failed to add message to Redis for thread {self.thread_id}: {e}"
            )
            raise

    async def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation"""
        await self.add_message(Message("user", content))

    async def add_assistant_message(self, content: Any) -> None:
        """Add an assistant message to the conversation"""
        await self.add_message(Message("assistant", content))

    async def get_messages(
        self, max_messages: int = 10, roles: List[str] | None = None
    ) -> List[Union[Message, dict[str, Any]]]:
        """Get messages from the conversation, optionally filtered by role"""
        try:
            redis = await self._get_redis()

            # Get messages from Redis (most recent first due to lpush)
            # type: ignore
            message_jsons = await redis.lrange(self._message_key, 0, max_messages - 1)

            messages: List[Message] = []
            for message_json in message_jsons:
                try:
                    message_data = json.loads(message_json)
                    message = Message(
                        role=message_data["role"],
                        content=message_data["content"],
                        message_type=message_data.get("message_type", "text"),
                    )
                    message.timestamp = message_data["timestamp"]

                    # Filter by roles if specified
                    if roles is None or message.role in roles:
                        messages.append(message)

                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse message from Redis: {e}")
                    continue

            # Reverse to get chronological order (oldest first)
            messages.reverse()

            # Apply max_messages limit after filtering
            if max_messages and len(messages) > max_messages:
                messages = messages[-max_messages:]

            return [messages.to_dict() for messages in messages]

        except Exception as e:
            logger.error(
                f"Failed to get messages from Redis for thread {self.thread_id}: {e}"
            )
            return []

    async def clear(self) -> None:
        """Clear the conversation from Redis"""
        try:
            redis = await self._get_redis()

            # Delete all conversation data
            await redis.delete(self._message_key)
            await redis.delete(self._metadata_key)

            # Reset conversation info
            self.last_updated = datetime.now().isoformat()
            self.executions_count = 0

            conversation_data = {
                "thread_id": self.thread_id,
                "created_at": self.created_at,
                "last_updated": self.last_updated,
                "executions_count": self.executions_count,
            }
            # type: ignore
            await redis.hset(self._conversation_key, mapping=conversation_data)
            # type: ignore
            await redis.expire(self._conversation_key, 86400 * 30)

            logger.debug(f"Cleared conversation data for thread {self.thread_id}")

        except Exception as e:
            logger.error(
                f"Failed to clear conversation from Redis for thread {self.thread_id}: {e}"
            )
            raise

    async def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata for the conversation in Redis"""
        try:
            await self._initialize_conversation()
            redis = await self._get_redis()

            # Store metadata as JSON
            metadata_json = json.dumps(value)
            # type: ignore
            await redis.hset(self._metadata_key, key, metadata_json)
            await redis.expire(self._metadata_key, 86400 * 30)  # type: ignore

            logger.debug(f"Set metadata {key} for thread {self.thread_id}")

        except Exception as e:
            logger.error(
                f"Failed to set metadata in Redis for thread {self.thread_id}: {e}"
            )
            raise

    async def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata for the conversation from Redis"""
        try:
            redis = await self._get_redis()

            # type: ignore
            metadata_json = await redis.hget(self._metadata_key, key)
            if metadata_json is None:
                return default

            return json.loads(metadata_json)

        except (json.JSONDecodeError, Exception) as e:
            logger.error(
                f"Failed to get metadata from Redis for thread {self.thread_id}: {e}"
            )
            return default

    async def get_chat_history(
        self, as_string: bool = False, max_messages: int = 10
    ) -> Union[List[Message], str]:
        """Get the chat history in a format suitable for LLM context"""
        try:
            messages = await self.get_messages(max_messages=max_messages)

            if as_string:
                history_parts = []
                for message in messages:
                    prefix = f"{message.role.capitalize()}: "
                    content = message.content
                    history_parts.append(f"{prefix}{content}")
                return "\n".join(history_parts)

            return messages

        except Exception as e:
            logger.error(
                f"Failed to get chat history from Redis for thread {self.thread_id}: {e}"
            )
            return [] if not as_string else ""

    async def get_conversation_info(self) -> Dict[str, Any]:
        """Get conversation metadata from Redis"""
        try:
            redis = await self._get_redis()

            info = await redis.hgetall(self._conversation_key)  # type: ignore
            if not info:
                return {}

            # Convert string values back to appropriate types
            result = {}
            for key, value in info.items():
                if key in ["executions_count"]:
                    result[key] = int(value)
                else:
                    result[key] = value

            return result

        except Exception as e:
            logger.error(
                f"Failed to get conversation info from Redis for thread {self.thread_id}: {e}"
            )
            return {}

    async def increment_executions(self) -> None:
        """Increment the execution count for this conversation"""
        try:
            redis = await self._get_redis()
            # type: ignore
            await redis.hincrby(self._conversation_key, "executions_count", 1)
            # type: ignore
            await redis.hset(
                self._conversation_key, "last_updated", datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(
                f"Failed to increment executions in Redis for thread {self.thread_id}: {e}"
            )
            raise

    async def delete_conversation(self) -> None:
        """Permanently delete the conversation from Redis"""
        try:
            redis = await self._get_redis()

            # Delete all keys related to this conversation
            await redis.delete(self._message_key)
            await redis.delete(self._metadata_key)
            await redis.delete(self._conversation_key)

            logger.info(f"Deleted conversation data for thread {self.thread_id}")

        except Exception as e:
            logger.error(
                f"Failed to delete conversation from Redis for thread {self.thread_id}: {e}"
            )
            raise


class ConversationMemory:
    """Class to maintain conversation history across workflow executions"""

    _instances: Dict[str, "BaseConversationMemory"] = {}

    @classmethod
    def get_instance(cls, thread_id: str) -> "BaseConversationMemory":
        """Get or create a conversation memory instance for a thread ID"""
        if thread_id not in cls._instances:
            logger.info(
                f"Creating new conversation memory instance for thread ID: {thread_id}"
            )
            if settings.REDIS_FOR_CONVERSATION:
                cls._instances[thread_id] = RedisConversationMemory(thread_id)
            else:
                cls._instances[thread_id] = InMemoryConversationMemory(thread_id)
        return cls._instances[thread_id]

    @classmethod
    def clear_all(cls) -> None:
        """Clear all conversation memories"""
        cls._instances.clear()
