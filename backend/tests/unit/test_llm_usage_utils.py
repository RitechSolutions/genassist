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

    def test_stamps_fallback_provider_id_when_present(self):
        from app.modules.workflow.llm.fallback_exceptions import FALLBACK_PROVIDER_ID_KEY

        class MockMessage:
            response_metadata = {
                "token_usage": {"prompt_tokens": 3, "completion_tokens": 4},
                FALLBACK_PROVIDER_ID_KEY: "provider-2",
            }

        result = extract_usage_from_aimessage(MockMessage())
        assert result["provider_id"] == "provider-2"
        assert result["input_tokens"] == 3 and result["output_tokens"] == 4

    def test_no_provider_id_key_when_absent(self):
        class MockMessage:
            response_metadata = {"token_usage": {"prompt_tokens": 1, "completion_tokens": 1}}

        result = extract_usage_from_aimessage(MockMessage())
        assert "provider_id" not in result

    def test_bedrock_converse_reads_usage_metadata_attribute(self):
        class MockMessage:
            usage_metadata = {
                "input_tokens": 11,
                "output_tokens": 7,
                "total_tokens": 18,
                "input_token_details": {"cache_read": 0, "cache_creation": 0},
            }
            response_metadata = {
                "ResponseMetadata": {"HTTPStatusCode": 200},
                "stopReason": "end_turn",
                "metrics": {"latencyMs": [123]},
                "model_provider": "bedrock_converse",
                "model_name": "eu.amazon.nova-2-lite-v1:0",
            }

        result = extract_usage_from_aimessage(MockMessage())
        assert result == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}

    def test_bedrock_claude_both_sources_agree(self):
        class MockMessage:
            usage_metadata = {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
            response_metadata = {"usage": {"prompt_tokens": 11, "completion_tokens": 7}}

        result = extract_usage_from_aimessage(MockMessage())
        assert result == {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}

    def test_usage_metadata_zeros_are_preserved(self):
        class MockMessage:
            usage_metadata = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            response_metadata = {}

        result = extract_usage_from_aimessage(MockMessage())
        assert result == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def test_stamps_fallback_provider_id_when_usage_from_attribute(self):
        from app.modules.workflow.llm.fallback_exceptions import FALLBACK_PROVIDER_ID_KEY

        class MockMessage:
            usage_metadata = {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
            response_metadata = {FALLBACK_PROVIDER_ID_KEY: "provider-9"}

        result = extract_usage_from_aimessage(MockMessage())
        assert result["provider_id"] == "provider-9"
        assert result["input_tokens"] == 11 and result["output_tokens"] == 7

    def test_non_dict_usage_metadata_falls_back_to_response_metadata(self):
        class MockMessage:
            usage_metadata = "garbage"
            response_metadata = {"token_usage": {"prompt_tokens": 2, "completion_tokens": 3}}

        result = extract_usage_from_aimessage(MockMessage())
        assert result == {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}

    def test_usage_metadata_missing_total_is_summed(self):
        class MockMessage:
            usage_metadata = {"input_tokens": 4, "output_tokens": 6}
            response_metadata = {}

        result = extract_usage_from_aimessage(MockMessage())
        assert result == {"input_tokens": 4, "output_tokens": 6, "total_tokens": 10}
