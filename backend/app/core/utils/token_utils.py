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

        try:
            import tiktoken

            encoding = tiktoken.get_encoding(self.encoding_name)
            self._encoding_cache[self.encoding_name] = encoding
            return encoding
        except ImportError:
            raise ImportError(
                "tiktoken library not installed. Install with: pip install tiktoken"
            )

    @property
    def encoding_name(self) -> str:
        """Get the appropriate encoding name for the model"""
        # GPT-5 and O1 series use o200k_base
        if any(
            prefix in self.model
            for prefix in ["gpt-5", "o1-", "o1-mini", "o1-small", "o1-medium", "o1-large"]
        ):
            return "o200k_base"

        # GPT-4, GPT-3.5-turbo and other models use cl100k_base
        if any(prefix in self.model for prefix in ["gpt-4", "gpt-3.5-turbo"]):
            return "cl100k_base"

        # Default to cl100k_base for unknown OpenAI models
        logger.warning(
            f"Unknown OpenAI model '{self.model}', defaulting to cl100k_base encoding"
        )
        return "cl100k_base"

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