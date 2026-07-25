"""Unit tests for Gemini Live per-turn usage extraction"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.workflow.agents.live_agent_gemini import GeminiLiveAgent


def _agent() -> GeminiLiveAgent:
    return GeminiLiveAgent(api_key="k", model="gemini-live", live_config={}, tools=[])


class TestExtractLiveUsage:
    def test_none_when_no_usage(self):
        a = _agent()
        assert a._extract_live_usage() is None

    def test_maps_prompt_and_tool_use_to_input(self):
        a = _agent()
        a._last_usage = SimpleNamespace(
            prompt_token_count=100,
            tool_use_prompt_token_count=20,
            response_token_count=40,
            thoughts_token_count=10,
            total_token_count=170,
            cached_content_token_count=5,
        )
        usage = a._extract_live_usage()
        assert usage["input_tokens"] == 120
        assert usage["output_tokens"] == 50
        assert usage["total_tokens"] == 170
        assert usage["token_details"]["cached_content_token_count"] == 5

    def test_total_falls_back_to_parts(self):
        a = _agent()
        a._last_usage = SimpleNamespace(
            prompt_token_count=10,
            response_token_count=5,
        )
        usage = a._extract_live_usage()
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 5
        assert usage["total_tokens"] == 15

    def test_all_zero_is_none(self):
        a = _agent()
        a._last_usage = SimpleNamespace(prompt_token_count=0, response_token_count=0, total_token_count=0)
        assert a._extract_live_usage() is None

    def test_total_never_below_parts(self):
        a = _agent()
        a._last_usage = SimpleNamespace(
            prompt_token_count=100, response_token_count=100, total_token_count=1
        )
        usage = a._extract_live_usage()
        assert usage["total_tokens"] == 200

    def test_candidates_count_is_used_when_response_count_is_absent(self):
        a = _agent()
        a._last_usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=7)
        usage = a._extract_live_usage()
        assert usage["output_tokens"] == 7
        assert usage["total_tokens"] == 17

    def test_response_and_candidates_are_never_summed(self):
        a = _agent()
        a._last_usage = SimpleNamespace(
            prompt_token_count=10, response_token_count=7, candidates_token_count=7
        )
        usage = a._extract_live_usage()
        assert usage["output_tokens"] == 7
        assert usage["token_details"]["candidates_token_count"] == 7

    def test_thought_tokens_add_to_the_reply(self):
        a = _agent()
        a._last_usage = SimpleNamespace(
            prompt_token_count=10, candidates_token_count=7, thoughts_token_count=3
        )
        assert a._extract_live_usage()["output_tokens"] == 10

    def test_resolved_model_travels_with_the_usage(self):
        a = _agent()
        a._last_usage = SimpleNamespace(prompt_token_count=1, response_token_count=1)
        assert a._extract_live_usage()["model"] == "gemini-live"


class TestPerTurnReset:
    @pytest.mark.asyncio
    async def test_finalize_clears_usage_for_the_next_turn(self):
        a = _agent()
        a._agent_tx = ["hello"]
        a._last_usage = SimpleNamespace(prompt_token_count=10, response_token_count=5)

        await a._finalize_turn(AsyncMock())

        assert a._last_usage is None
        assert a._extract_live_usage() is None

    @pytest.mark.asyncio
    async def test_reset_happens_even_when_the_turn_is_not_persisted(self):
        a = _agent()
        a._last_usage = SimpleNamespace(prompt_token_count=10, response_token_count=5)

        await a._finalize_turn(AsyncMock())

        assert a._last_usage is None
