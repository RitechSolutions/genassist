"""Pins on how the installed provider SDKs report cached tokens"""

from types import SimpleNamespace

from langchain_anthropic.chat_models import _create_usage_metadata
from langchain_aws.chat_models.bedrock_converse import _extract_usage_metadata

from app.core.config.llm_pricing import CACHE_EXCLUSIVE_PROVIDERS


class TestAnthropicReportsInclusiveInput:
    def test_cache_buckets_are_summed_into_input_tokens(self):
        usage = _create_usage_metadata(
            SimpleNamespace(
                input_tokens=100,
                output_tokens=10,
                cache_read_input_tokens=500,
                cache_creation_input_tokens=60,
                cache_creation=None,
            )
        )
        assert usage["input_tokens"] == 660
        assert usage["total_tokens"] == 670
        assert usage["input_token_details"] == {"cache_read": 500, "cache_creation": 60}

    def test_anthropic_is_not_treated_as_exclusive(self):
        assert "anthropic" not in CACHE_EXCLUSIVE_PROVIDERS


class TestBedrockReportsExclusiveInput:
    def test_cache_buckets_are_left_out_of_input_tokens(self):
        response = {
            "usage": {
                "inputTokens": 100,
                "outputTokens": 10,
                "totalTokens": 610,
                "cacheReadInputTokens": 500,
                "cacheWriteInputTokens": 0,
            }
        }
        usage = _extract_usage_metadata(response)
        assert usage["input_tokens"] == 100
        assert usage["total_tokens"] == 610
        assert usage["input_token_details"] == {"cache_read": 500, "cache_creation": 0}
        assert "usage" not in response

    def test_bedrock_is_treated_as_exclusive(self):
        assert "bedrock" in CACHE_EXCLUSIVE_PROVIDERS
