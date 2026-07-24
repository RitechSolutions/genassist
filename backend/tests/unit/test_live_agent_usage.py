"""Unit tests for Gemini Live per-turn usage extraction"""

from types import SimpleNamespace

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
