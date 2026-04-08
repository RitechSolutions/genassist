"""Unit tests for LLM usage extraction utilities."""

import pytest

from app.core.utils.llm_usage_utils import (
    extract_usage_from_response_metadata,
    extract_usage_from_aimessage,
)


class TestExtractUsageFromResponseMetadata:
    def test_openai_token_usage(self):
        metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 20}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}

    def test_anthropic_usage(self):
        metadata = {"usage": {"input_tokens": 5, "output_tokens": 15}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 5, "output_tokens": 15, "total_tokens": 20}

    def test_google_usage_metadata(self):
        metadata = {
            "usage_metadata": {
                "prompt_token_count": 100,
                "candidates_token_count": 50,
            }
        }
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}

    def test_empty_metadata_returns_none(self):
        assert extract_usage_from_response_metadata({}) is None
        assert extract_usage_from_response_metadata(None) is None

    def test_missing_usage_returns_none(self):
        metadata = {"model": "gpt-4o", "finish_reason": "stop"}
        assert extract_usage_from_response_metadata(metadata) is None


class TestExtractUsageFromAIMessage:
    def test_with_response_metadata(self):
        class MockMessage:
            response_metadata = {"token_usage": {"prompt_tokens": 8, "completion_tokens": 12}}

        result = extract_usage_from_aimessage(MockMessage())
        assert result == {"input_tokens": 8, "output_tokens": 12, "total_tokens": 20}

    def test_none_message_returns_none(self):
        assert extract_usage_from_aimessage(None) is None
