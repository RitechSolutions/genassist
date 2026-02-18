"""
Token counting utilities for LLM context management.

This module provides token counting functionality with provider-specific strategies:
- OpenAI models: Use tiktoken library for accurate token counts
- Other providers: Use character-based approximation (1 token ≈ 3.75 characters)
"""

from typing import Dict, Any, List
import logging
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class TokenCounter(ABC):
    """Base class for token counting strategies"""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens
        """
        pass


class TiktokenCounter(TokenCounter):
    """OpenAI-specific token counter using tiktoken library"""

    # Cache for tiktoken encodings
    _encoding_cache: Dict[str, Any] = {}

    def __init__(self, model: str):
        """
        Initialize tiktoken counter for a specific model.

        Args:
            model: OpenAI model name (e.g., "gpt-4o", "gpt-3.5-turbo")
        """
        self.model = model.lower()
        self.encoding = self._get_encoding()

    def _get_encoding(self):
        """Get or create tiktoken encoding for the model"""
        if self.encoding_name in self._encoding_cache:
            return self._encoding_cache[self.encoding_name]

        import tiktoken
        encoding = tiktoken.get_encoding(self.encoding_name)
        self._encoding_cache[self.encoding_name] = encoding
        return encoding


    @property
    def encoding_name(self) -> str:
        """Get the appropriate encoding name for the model"""
        from app.core.utils.gpt_utils import get_openai_encoding_name
        return get_openai_encoding_name(self.model)

    def count_tokens(self, text: str) -> int:
        """
        Count tokens using tiktoken.

        Args:
            text: The text to count tokens for

        Returns:
            Accurate token count
        """
        if not text:
            return 0

        try:
            tokens = self.encoding.encode(text)
            return len(tokens)
        except Exception as e:
            # Log and fallback to approximation if tiktoken fails
            logger.warning(
                f"tiktoken encoding failed for model {self.model}: {e}. Using approximation."
            )
            return int(len(text) / 3.75)


class ApproximateTokenCounter(TokenCounter):
    """Character-based approximation for non-OpenAI models"""

    CHARS_PER_TOKEN = 3.75

    def count_tokens(self, text: str) -> int:
        """
        Approximate token count using character-based formula.

        Args:
            text: The text to count tokens for

        Returns:
            Approximate token count (1 token ≈ 3.75 characters)
        """
        if not text:
            return 0

        return int(len(text) / self.CHARS_PER_TOKEN)


def get_token_counter(provider: str, model: str) -> TokenCounter:
    """
    Factory function to get the appropriate token counter for a provider/model.

    Args:
        provider: LLM provider name (e.g., "openai", "anthropic", "google_genai")
        model: Model name (e.g., "gpt-4o", "claude-3-sonnet")

    Returns:
        TokenCounter instance (TiktokenCounter or ApproximateTokenCounter)
    """
    if provider.lower() == "openai":
        return TiktokenCounter(model)

    return ApproximateTokenCounter()


def count_message_tokens(
    messages: List[Dict[str, Any]], counter: TokenCounter
) -> int:
    """
    Count total tokens in a list of messages including formatting overhead.

    For OpenAI-style chat format, each message has overhead:
    - role name: ~1 token
    - message separators: ~3 tokens
    - Total: ~4 tokens per message overhead

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        counter: TokenCounter instance to use

    Returns:
        Total token count including message formatting overhead
    """
    if not messages:
        return 0

    total_tokens = 0

    for message in messages:
        # Count tokens in role
        role = message.get("role", "")
        total_tokens += counter.count_tokens(role)

        # Count tokens in content
        content = message.get("content", "")
        if isinstance(content, str):
            total_tokens += counter.count_tokens(content)
        elif isinstance(content, list):
            # Handle multimodal content (list of dicts)
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    total_tokens += counter.count_tokens(item["text"])

        # Add message formatting overhead (~3 tokens per message)
        total_tokens += 3

    # Add conversation-level overhead (~3 tokens)
    total_tokens += 3

    return total_tokens


def estimate_string_tokens(text: str, provider: str, model: str) -> int:
    """
    Quick token estimation for a single string.

    Args:
        text: Text to estimate tokens for
        provider: Provider name
        model: Model name

    Returns:
        Estimated token count
    """
    counter = get_token_counter(provider, model)
    return counter.count_tokens(text)


def calculate_history_tokens(config: dict[str, Any], model: str, provider:str, system_prompt: str,
                                   user_prompt: str) -> int:
    TOTAL_TOKEN_DEFAULT = 10000 # declared in frontend component as well
    TOTAL_CONVERSATION_HISTORY_DEFAULT= 5000 # declared in frontend component as well
    # Get token counter
    counter = get_token_counter(provider, model)

    # Count actual tokens in prompts
    system_tokens = counter.count_tokens(system_prompt)
    user_tokens = counter.count_tokens(user_prompt)

    # Get configuration
    total_budget = config.get("tokenBudget", TOTAL_TOKEN_DEFAULT)
    requested_history_tokens = config.get("conversationHistoryTokens", TOTAL_CONVERSATION_HISTORY_DEFAULT)

    # Calculate if we need to reduce history allocation
    needed = system_tokens + user_tokens + requested_history_tokens

    if needed > total_budget:
        # Reduce history to fit within budget
        actual_history_tokens = total_budget - system_tokens - user_tokens
        actual_history_tokens = max(0, actual_history_tokens)  # Ensure non-negative
        logger.warning(
                f"Token budget exceeded. Requested history: {requested_history_tokens}, "
                f"reduced to: {actual_history_tokens} (Total: {total_budget}, "
                f"System: {system_tokens}, User: {user_tokens})"
                )
    else:
        # Within budget, use requested allocation
        actual_history_tokens = requested_history_tokens
    return actual_history_tokens
