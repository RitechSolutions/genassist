"""Unit tests for LLM usage extraction utilities."""

from app.core.utils.llm_usage_utils import (
    USAGE_METADATA_MISSING,
    extract_cache_tokens,
    extract_usage_from_aimessage,
    extract_usage_from_response_metadata,
    is_usage_metadata_missing,
    usage_or_placeholder,
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

    def test_explicit_zero_usage_is_reported_not_none(self):
        metadata = {"token_usage": {"prompt_tokens": 0, "completion_tokens": 0}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def test_zero_input_with_nonzero_output_preserved(self):
        metadata = {"usage": {"input_tokens": 0, "output_tokens": 5}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 5, "total_tokens": 5}

    def test_google_zero_candidates_preserved(self):
        metadata = {"usage_metadata": {"prompt_token_count": 100, "candidates_token_count": 0}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 100, "output_tokens": 0, "total_tokens": 100}

    def test_top_level_zeros_are_reported(self):
        metadata = {"input_tokens": 0, "output_tokens": 0}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def test_zero_from_first_source_not_overwritten_by_later_source(self):
        metadata = {
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 4},
            "usage_metadata": {"prompt_token_count": 999, "candidates_token_count": 999},
        }
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 4, "total_tokens": 4}

    def test_gap_fill_across_sources(self):
        metadata = {
            "token_usage": {"prompt_tokens": 5},
            "usage": {"output_tokens": 7},
        }
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 5, "output_tokens": 7, "total_tokens": 12}

    def test_non_numeric_junk_is_skipped_not_crashing(self):
        metadata = {"token_usage": {"prompt_tokens": "", "completion_tokens": 42}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 42, "total_tokens": 42}

    def test_top_level_junk_is_skipped_not_crashing(self):
        metadata = {"input_tokens": [], "output_tokens": 3}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 3, "total_tokens": 3}

    def test_anthropic_junk_is_skipped_not_crashing(self):
        metadata = {"usage": {"input_tokens": "", "output_tokens": 5}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 5, "total_tokens": 5}

    def test_all_junk_returns_none(self):
        metadata = {"token_usage": {"prompt_tokens": "", "completion_tokens": {}}}
        assert extract_usage_from_response_metadata(metadata) is None

    def test_booleans_are_not_token_counts(self):
        metadata = {"token_usage": {"prompt_tokens": True, "completion_tokens": 9}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 9, "total_tokens": 9}

    def test_negative_counts_clamp_to_zero(self):
        metadata = {"usage": {"input_tokens": -5, "output_tokens": 4}}
        result = extract_usage_from_response_metadata(metadata)
        assert result == {"input_tokens": 0, "output_tokens": 4, "total_tokens": 4}

    def test_non_finite_counts_are_skipped(self):
        metadata = {"usage": {"input_tokens": float("nan"), "output_tokens": float("inf")}}
        assert extract_usage_from_response_metadata(metadata) is None

    def test_provider_total_above_parts_is_kept(self):
        metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 40}}
        result = extract_usage_from_response_metadata(metadata)
        assert result["total_tokens"] == 40

    def test_provider_total_below_parts_is_raised_to_the_sum(self):
        metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 1}}
        result = extract_usage_from_response_metadata(metadata)
        assert result["total_tokens"] == 15


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
        assert result == {
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
            "token_details": {"input_token_details": {"cache_read": 0, "cache_creation": 0}},
        }

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

    def test_provider_total_above_parts_is_kept(self):
        class MockMessage:
            usage_metadata = {"input_tokens": 4, "output_tokens": 6, "total_tokens": 30}
            response_metadata = {}

        assert extract_usage_from_aimessage(MockMessage())["total_tokens"] == 30

    def test_output_token_details_are_preserved(self):
        class MockMessage:
            usage_metadata = {
                "input_tokens": 4,
                "output_tokens": 6,
                "output_token_details": {"reasoning": 2},
            }
            response_metadata = {}

        result = extract_usage_from_aimessage(MockMessage())
        assert result["token_details"] == {"output_token_details": {"reasoning": 2}}

    def test_empty_token_details_are_not_attached(self):
        class MockMessage:
            usage_metadata = {"input_tokens": 4, "output_tokens": 6, "input_token_details": {}}
            response_metadata = {}

        assert "token_details" not in extract_usage_from_aimessage(MockMessage())

    def test_message_without_any_usage_returns_none(self):
        class MockMessage:
            usage_metadata = None
            response_metadata = {"finish_reason": "stop"}

        assert extract_usage_from_aimessage(MockMessage()) is None


class TestUsagePlaceholder:
    def test_missing_usage_becomes_zero_token_marked_entry(self):
        entry = usage_or_placeholder(None)
        assert entry["input_tokens"] == 0 and entry["output_tokens"] == 0 and entry["total_tokens"] == 0
        assert entry["token_details"] == {USAGE_METADATA_MISSING: True}
        assert is_usage_metadata_missing(entry["token_details"])

    def test_present_usage_is_copied_not_marked(self):
        usage = {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7}
        entry = usage_or_placeholder(usage)
        assert entry == usage
        assert entry is not usage
        assert not is_usage_metadata_missing(entry.get("token_details"))

    def test_marker_check_tolerates_non_dicts(self):
        assert is_usage_metadata_missing(None) is False
        assert is_usage_metadata_missing("junk") is False
        assert is_usage_metadata_missing({"cache_read": 1}) is False


class TestExtractCacheTokens:
    def test_standard_nested_details(self):
        details = {"input_token_details": {"cache_read": 3697, "cache_creation": 60}}
        assert extract_cache_tokens(details) == (3697, 60)

    def test_flat_details_shape(self):
        assert extract_cache_tokens({"cache_read": 12, "cache_creation": 34}) == (12, 34)

    def test_nested_wins_over_flat_when_both_present(self):
        details = {"cache_read": 1, "input_token_details": {"cache_read": 500, "cache_creation": 7}}
        assert extract_cache_tokens(details) == (500, 7)

    def test_empty_nested_details_fall_back_to_the_blob(self):
        assert extract_cache_tokens({"input_token_details": {}, "cache_read": 9}) == (9, 0)

    def test_non_dict_nested_details_fall_back_to_the_blob(self):
        assert extract_cache_tokens({"input_token_details": "junk", "cache_creation": 4}) == (0, 4)

    def test_missing_buckets_are_zero(self):
        assert extract_cache_tokens({"input_token_details": {"audio": 10}}) == (0, 0)
        assert extract_cache_tokens({}) == (0, 0)

    def test_partial_buckets_keep_the_reported_one(self):
        assert extract_cache_tokens({"input_token_details": {"cache_read": 500}}) == (500, 0)
        assert extract_cache_tokens({"input_token_details": {"cache_creation": 500}}) == (0, 500)

    def test_explicit_zeros_are_zero(self):
        assert extract_cache_tokens({"input_token_details": {"cache_read": 0, "cache_creation": 0}}) == (0, 0)

    def test_none_and_non_dicts(self):
        assert extract_cache_tokens(None) == (0, 0)
        assert extract_cache_tokens("junk") == (0, 0)
        assert extract_cache_tokens(42) == (0, 0)
        assert extract_cache_tokens([{"cache_read": 5}]) == (0, 0)

    def test_usage_metadata_missing_sentinel(self):
        assert extract_cache_tokens({USAGE_METADATA_MISSING: True}) == (0, 0)

    def test_junk_values_count_as_zero(self):
        details = {"input_token_details": {"cache_read": "500", "cache_creation": None}}
        assert extract_cache_tokens(details) == (0, 0)

    def test_booleans_are_not_token_counts(self):
        assert extract_cache_tokens({"input_token_details": {"cache_read": True}}) == (0, 0)

    def test_non_finite_values_count_as_zero(self):
        details = {"input_token_details": {"cache_read": float("inf"), "cache_creation": float("nan")}}
        assert extract_cache_tokens(details) == (0, 0)

    def test_negative_counts_clamp_to_zero(self):
        details = {"input_token_details": {"cache_read": -5, "cache_creation": -1}}
        assert extract_cache_tokens(details) == (0, 0)

    def test_anthropic_ephemeral_keys_are_ignored(self):
        details = {
            "input_token_details": {
                "cache_read": 100,
                "cache_creation": 200,
                "ephemeral_5m_input_tokens": 200,
                "ephemeral_1h_input_tokens": None,
            }
        }
        assert extract_cache_tokens(details) == (100, 200)

    def test_floats_truncate_to_int(self):
        assert extract_cache_tokens({"input_token_details": {"cache_read": 12.9}}) == (12, 0)
