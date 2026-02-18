from typing import Dict, Any, List, Union, Optional
import logging
from datetime import datetime
import json
from redis.asyncio import Redis
from app.dependencies.dependency_injection import RedisString
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

    async def add_input_output(self, input: str, output: str) -> None:
        """Add an input and output to the conversation"""
        await self.add_user_message(input)
        await self.add_assistant_message(output)

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

    async def get_chat_history_within_tokens(
        self,
        token_budget: int,
        provider: str,
        model: str,
        as_string: bool = False
    ) -> Union[List[dict[str, Any]], str]:
        """
        Get formatted chat history within token budget.

        Args:
            token_budget: Maximum tokens for history
            provider: LLM provider name (e.g., 'openai', 'anthropic')
            model: Model name for tokenization (e.g., 'gpt-4o')
            as_string: If True, return formatted string; else list of dicts

        Returns:
            Formatted chat history within token budget
        """
        raise NotImplementedError

    async def needs_compaction(self, threshold: int) -> bool:
        """
        Check if conversation needs compaction based on total message count.

        Args:
            threshold: Message count threshold for triggering compaction

        Returns:
            True if total messages exceed threshold and compaction hasn't run recently
        """
        raise NotImplementedError

    async def get_compacted_summary(self) -> Optional[Dict[str, Any]]:
        """
        Get the current compacted summary (entities + prose).

        Returns:
            Dictionary with:
            - entities: List of extracted facts/entities in JSON format
            - prose_summary: Natural language summary
            - compacted_until_timestamp: ISO timestamp of last message in compacted range
            - compacted_message_count: Number of messages that were compacted
            - last_compaction_timestamp: When compaction was performed
            Or None if no compaction exists
        """
        raise NotImplementedError

    async def set_compacted_summary(self, summary: Dict[str, Any]) -> None:
        """
        Store a compacted summary.

        Args:
            summary: Dictionary with entities, prose_summary, metadata
        """
        raise NotImplementedError

    async def get_messages_for_compaction(
        self, keep_recent: int
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Get messages split into compaction candidates and recent messages to keep.

        Args:
            keep_recent: Number of most recent messages to exclude from compaction

        Returns:
            Tuple of (messages_to_compact, messages_to_keep)
            Only returns messages that haven't been compacted yet
        """
        raise NotImplementedError

    async def get_chat_history_with_compaction(
        self, max_messages: int, as_string: bool = False
    ) -> Union[List[Dict[str, Any]], str]:
        """
        Get chat history with compacted summary prepended.

        This method retrieves:
        1. Compacted summary (if it exists) as a synthetic "system" message
        2. Most recent N messages (uncompacted)

        Args:
            max_messages: Number of recent messages to include
            as_string: If True, return formatted string; else list of dicts

        Returns:
            Chat history with compacted context
        """
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

    async def get_chat_history_within_tokens(
        self,
        token_budget: int,
        provider: str,
        model: str,
        as_string: bool = False
    ) -> Union[List[dict[str, Any]], str]:
        """Get formatted chat history within token budget"""
        from app.core.utils.token_utils import get_token_counter

        if token_budget <= 0:
            raise ValueError("Token budget must be positive")

        counter = get_token_counter(provider, model)
        selected_messages = []
        current_tokens = 0

        # Iterate from most recent to oldest
        for message in reversed(self.messages):
            # Count tokens for this message
            message_dict = message.to_dict()
            message_tokens = counter.count_tokens(
                f"{message_dict['role']}: {message_dict['content']}"
            )

            # Check if adding this message would exceed budget
            if current_tokens + message_tokens > token_budget:
                # If we have no messages yet, include at least this one
                if not selected_messages:
                    selected_messages.append(message_dict)
                break

            selected_messages.append(message_dict)
            current_tokens += message_tokens

        # Reverse to get chronological order (oldest to newest)
        selected_messages.reverse()

        if as_string:
            history_parts = []
            for msg in selected_messages:
                prefix = f"{msg['role'].capitalize()}: "
                content = msg['content']
                history_parts.append(f"{prefix}{content}")
            return "\n".join(history_parts)

        return selected_messages

    async def needs_compaction(self, threshold: int) -> bool:
        """Check if compaction is needed at threshold intervals"""
        total_messages = len(self.messages)

        if total_messages < threshold:
            return False

        # Check if we need to compact again at next threshold
        summary = await self.get_compacted_summary()
        if summary:
            compacted_count = summary.get("compacted_message_count", 0)
            # Compact every threshold messages (at 20, 40, 60, 80...)
            if total_messages < compacted_count + threshold:
                return False

        return True

    async def get_compacted_summary(self) -> Optional[Dict[str, Any]]:
        """Retrieve stored compacted summary (entities + prose)"""
        return self.metadata.get("compacted_summary")

    async def set_compacted_summary(self, summary: Dict[str, Any]) -> None:
        """Store compacted summary in metadata"""
        self.metadata["compacted_summary"] = summary

    async def get_messages_for_compaction(
        self, keep_recent: int
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Split messages into (to_compact, to_keep) based on what's already compacted"""
        total_messages = len(self.messages)
        summary = await self.get_compacted_summary()

        # Determine starting point for compaction
        if summary:
            # Already compacted some messages
            already_compacted = summary.get("compacted_message_count", 0)
            # Messages to consider for new compaction (exclude already compacted + recent)
            start_index = already_compacted
        else:
            # First time compacting
            start_index = 0

        # Calculate split point
        # Keep the last 'keep_recent' messages uncompacted
        split_index = max(start_index, total_messages - keep_recent)

        if split_index <= start_index:
            # No new messages to compact
            return ([], self.messages[-keep_recent:] if keep_recent > 0 else [])

        # Messages to compact (from start_index to split_index)
        to_compact = [m.to_dict() for m in self.messages[start_index:split_index]]
        # Messages to keep recent (last keep_recent messages)
        to_keep = [m.to_dict() for m in self.messages[-keep_recent:]] if keep_recent > 0 else []

        return (to_compact, to_keep)

    async def get_chat_history_with_compaction(
        self, max_messages: int, as_string: bool = False
    ) -> Union[List[Dict[str, Any]], str]:
        """Get history with compacted summary prepended as synthetic system message"""
        summary = await self.get_compacted_summary()
        recent_messages = await self.get_messages(max_messages=max_messages)

        result = []

        # Add compacted summary as synthetic system message
        if summary and (summary.get("prose_summary") or summary.get("entities")):
            summary_content = self._format_compacted_summary(summary)
            result.append({
                "role": "system",
                "content": summary_content,
                "message_type": "compacted_summary",
                "timestamp": summary.get("last_compaction_timestamp")
            })

        # Add recent messages
        result.extend(recent_messages)

        if as_string:
            history_parts = []
            for msg in result:
                prefix = f"{msg['role'].capitalize()}: "
                history_parts.append(f"{prefix}{msg['content']}")
            return "\n".join(history_parts)

        return result

    def _format_compacted_summary(self, summary: Dict[str, Any]) -> str:
        """Format compacted summary for inclusion in chat history"""
        parts = ["[Conversation History Summary]"]

        if summary.get("prose_summary"):
            parts.append(f"\nContext: {summary['prose_summary']}")

        if summary.get("entities"):
            parts.append("\nKey Information:")
            for entity in summary["entities"][:20]:  # Limit to avoid token bloat
                entity_type = entity.get("type", "fact")
                if entity_type == "person":
                    parts.append(f"- Person: {entity.get('name', 'Unknown')}")
                elif entity_type == "preference":
                    parts.append(f"- User preference: {entity.get('description', '')}")
                else:
                    parts.append(f"- {entity.get('description', '')}")

        if summary.get("compacted_message_count"):
            parts.append(f"\n(Summary represents {summary['compacted_message_count']} earlier messages)")

        return "\n".join(parts)


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

            self.redis_client = injector.get(RedisString)
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

        except Exception as e:
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
                    prefix = f"{message['role'].capitalize()}: "
                    content = message["content"]
                    history_parts.append(f"{prefix}{content}")
                return "\n".join(history_parts)

            return messages

        except Exception as e:
            logger.error(
                f"Failed to get chat history from Redis for thread {self.thread_id}: {e}"
            )
            return [] if not as_string else ""

    async def get_chat_history_within_tokens(
        self,
        token_budget: int,
        provider: str,
        model: str,
        as_string: bool = False
    ) -> Union[List[dict[str, Any]], str]:
        """Get formatted chat history within token budget"""
        from app.core.utils.token_utils import get_token_counter

        if token_budget <= 0:
            return "" if as_string else []

        counter = get_token_counter(provider, model)
        redis = await self._get_redis()

        # Fetch a larger batch initially to minimize round-trips
        # Most conversations won't need more than 50 messages
        batch_size = 50
        message_jsons = await redis.lrange(self._message_key, 0, batch_size - 1)

        if not message_jsons:
            return "" if as_string else []

        selected_messages = []
        current_tokens = 0

        # Process messages (stored newest-first in Redis)
        for message_json in message_jsons:
            try:
                message_data = json.loads(message_json)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse message from Redis: {e}")
                continue

            # Count tokens for this message
            message_tokens = counter.count_tokens(
                f"{message_data['role']}: {message_data['content']}"
            )

            # Check if adding this message would exceed budget
            if current_tokens + message_tokens > token_budget:
                # If we have no messages yet, include at least this one
                if not selected_messages:
                    selected_messages.append(message_data)
                break

            selected_messages.append(message_data)
            current_tokens += message_tokens

        # Reverse to get chronological order (oldest to newest)
        selected_messages.reverse()

        if as_string:
            history_parts = []
            for msg in selected_messages:
                prefix = f"{msg['role'].capitalize()}: "
                content = msg['content']
                history_parts.append(f"{prefix}{content}")
            return "\n".join(history_parts)

        return selected_messages

    async def needs_compaction(self, threshold: int) -> bool:
        """Check if compaction is needed at threshold intervals"""
        try:
            redis = await self._get_redis()
            # Get total message count using llen
            total_messages = await redis.llen(self._message_key)  # type: ignore

            if total_messages < threshold:
                return False

            # Check if we need to compact again at next threshold
            summary = await self.get_compacted_summary()
            if summary:
                compacted_count = summary.get("compacted_message_count", 0)
                # Compact every threshold messages (at 20, 40, 60, 80...)
                if total_messages < compacted_count + threshold:
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to check compaction need for thread {self.thread_id}: {e}")
            return False

    async def get_compacted_summary(self) -> Optional[Dict[str, Any]]:
        """Retrieve stored compacted summary (entities + prose)"""
        return await self.get_metadata("compacted_summary")

    async def set_compacted_summary(self, summary: Dict[str, Any]) -> None:
        """Store compacted summary in metadata"""
        await self.set_metadata("compacted_summary", summary)

    async def get_messages_for_compaction(
        self, keep_recent: int
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Split messages into (to_compact, to_keep) based on what's already compacted"""
        redis = await self._get_redis()
        total_messages = await redis.llen(self._message_key)  # type: ignore
        summary = await self.get_compacted_summary()

        # Determine starting point for compaction
        if summary:
            # Already compacted some messages
            already_compacted = summary.get("compacted_message_count", 0)
            start_index = already_compacted
        else:
            # First time compacting
            start_index = 0

        # Calculate split point
        # Keep the last 'keep_recent' messages uncompacted
        split_index = max(start_index, total_messages - keep_recent)

        if split_index <= start_index:
            # No new messages to compact
            recent_messages = await self.get_messages(max_messages=keep_recent)
            return [], recent_messages

        # Fetch messages to compact
        # Redis stores newest first (lpush), so we need to calculate indices correctly
        # Messages from oldest to newest would be at indices (total-1) down to 0
        # We want messages from start_index to split_index (in chronological order)
        # In Redis terms: from (total - split_index) to (total - start_index - 1)
        redis_start = total_messages - split_index
        redis_end = total_messages - start_index - 1

        to_compact_jsons = await redis.lrange(
            self._message_key, redis_start, redis_end
        )  # type: ignore

        to_compact = []
        for message_json in reversed(to_compact_jsons):  # Reverse to get chronological order
            try:
                message_data = json.loads(message_json)
                to_compact.append(message_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse message from Redis: {e}")
                continue

        # Get recent messages to keep
        to_keep = await self.get_messages(max_messages=keep_recent)

        return to_compact, to_keep

    async def get_chat_history_with_compaction(
        self, max_messages: int, as_string: bool = False
    ) -> Union[List[Dict[str, Any]], str]:
        """Get history with compacted summary prepended as synthetic system message"""
        try:
            summary = await self.get_compacted_summary()
            recent_messages = await self.get_messages(max_messages=max_messages)

            result = []

            # Add compacted summary as synthetic system message
            if summary and (summary.get("prose_summary") or summary.get("entities")):
                summary_content = self._format_compacted_summary(summary)
                result.append({
                    "role": "system",
                    "content": summary_content,
                    "message_type": "compacted_summary",
                    "timestamp": summary.get("last_compaction_timestamp")
                })

            # Add recent messages
            result.extend(recent_messages)

            if as_string:
                history_parts = []
                for msg in result:
                    prefix = f"{msg['role'].capitalize()}: "
                    history_parts.append(f"{prefix}{msg['content']}")
                return "\n".join(history_parts)

            return result

        except Exception as e:
            logger.error(f"Failed to get chat history with compaction for thread {self.thread_id}: {e}")
            return "" if as_string else []

    def _format_compacted_summary(self, summary: Dict[str, Any]) -> str:
        """Format compacted summary for inclusion in chat history"""
        parts = ["[Conversation History Summary]"]

        if summary.get("prose_summary"):
            parts.append(f"\nContext: {summary['prose_summary']}")

        if summary.get("entities"):
            parts.append("\nKey Information:")
            for entity in summary["entities"][:20]:  # Limit to avoid token bloat
                entity_type = entity.get("type", "fact")
                if entity_type == "person":
                    parts.append(f"- Person: {entity.get('name', 'Unknown')}")
                elif entity_type == "preference":
                    parts.append(f"- User preference: {entity.get('description', '')}")
                else:
                    parts.append(f"- {entity.get('description', '')}")

        if summary.get("compacted_message_count"):
            parts.append(f"\n(Summary represents {summary['compacted_message_count']} earlier messages)")

        return "\n".join(parts)

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
