"""Unit tests for the node-level usage capture helpers"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.utils.llm_usage_utils import USAGE_METADATA_MISSING
from app.modules.workflow.engine.llm_usage_tracking import (
    merge_llm_usage_from_result,
    record_compaction_usage,
    record_node_llm_usage,
    resolve_provider_model,
)


class FakeState:

    def __init__(self):
        self.llm_usage = []

    def add_llm_usage(self, **kwargs):
        self.llm_usage.append(kwargs)


def _message(usage=None):
    return SimpleNamespace(usage_metadata=usage, response_metadata={})


def _patch_provider_service(providers=None, error=None):
    service = MagicMock()
    if error is not None:
        service.get_by_id = AsyncMock(side_effect=error)
    else:
        service.get_by_id = AsyncMock(
            side_effect=lambda pid: (providers or {})[str(pid)]
        )
    inj = MagicMock()
    inj.get = MagicMock(return_value=service)
    return patch("app.dependencies.injector.injector", inj), service


def _provider(provider="OpenAI", model="gpt-4o", prompt_caching_enabled=None):
    connection_data = {"api_key": "k"}
    if prompt_caching_enabled is not None:
        connection_data["prompt_caching_enabled"] = prompt_caching_enabled
    return SimpleNamespace(llm_model_provider=provider, llm_model=model, connection_data=connection_data)


class TestResolveProviderModel:
    @pytest.mark.asyncio
    async def test_lowercases_provider_and_keeps_model(self):
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            assert await resolve_provider_model("p1") == ("openai", "gpt-4o")

    @pytest.mark.asyncio
    async def test_lookup_failure_returns_blank_keys(self):
        ctx, _ = _patch_provider_service(error=RuntimeError("provider table down"))
        with ctx:
            assert await resolve_provider_model("p1") == ("", "")

    @pytest.mark.asyncio
    async def test_missing_id_skips_the_lookup(self):
        ctx, service = _patch_provider_service({"p1": _provider()})
        with ctx:
            assert await resolve_provider_model(None) == ("", "")
        service.get_by_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_memoizes_per_id(self):
        cache = {}
        ctx, service = _patch_provider_service({"p1": _provider(), "p2": _provider("Anthropic", "claude-3-opus")})
        with ctx:
            await resolve_provider_model("p1", cache)
            await resolve_provider_model("p1", cache)
            await resolve_provider_model("p2", cache)
        assert service.get_by_id.await_count == 2

    @pytest.mark.asyncio
    async def test_resolution_is_names_only(self):
        ctx, _ = _patch_provider_service({"p1": _provider("Anthropic", "claude-3-opus", prompt_caching_enabled=True)})
        with ctx:
            assert await resolve_provider_model("p1") == ("anthropic", "claude-3-opus")


class TestTheLegacyStoredKeyIsNeverRead:

    @pytest.mark.asyncio
    async def test_a_stored_opt_in_does_not_mark_usage(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider("Anthropic", "claude-3-opus", prompt_caching_enabled=True)})
        with ctx:
            await merge_llm_usage_from_result(state, {"llm_usage": [{"input_tokens": 1}]}, "node-1", "p1")

        assert state.llm_usage[0]["prompt_caching_enabled"] is False

    @pytest.mark.asyncio
    async def test_the_stored_connection_data_is_never_rewritten(self):
        provider = _provider("Anthropic", "claude-3-opus", prompt_caching_enabled=True)
        ctx, _ = _patch_provider_service({"p1": provider})
        with ctx:
            await resolve_provider_model("p1")

        assert provider.connection_data["prompt_caching_enabled"] is True


class TestMergeLlmUsageFromResult:
    @pytest.mark.asyncio
    async def test_records_entry_with_resolved_attribution(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider()})
        result = {"llm_usage": [{"input_tokens": 10, "output_tokens": 4, "total_tokens": 20, "purpose": "chat"}]}
        with ctx:
            await merge_llm_usage_from_result(state, result, "node-1", "p1")

        entry = state.llm_usage[0]
        assert entry["provider"] == "openai" and entry["model"] == "gpt-4o"
        assert entry["total_tokens"] == 20
        assert entry["purpose"] == "chat" and entry["node_id"] == "node-1"
        assert entry["llm_provider_id"] == "p1"
        assert entry["prompt_caching_enabled"] is False

    @pytest.mark.asyncio
    async def test_per_item_provider_id_overrides_the_node_primary(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider(), "p2": _provider("Anthropic", "claude-3-opus")})
        result = {"llm_usage": [{"input_tokens": 1, "output_tokens": 1, "provider_id": "p2"}]}
        with ctx:
            await merge_llm_usage_from_result(state, result, "node-1", "p1")

        assert state.llm_usage[0]["provider"] == "anthropic"
        assert state.llm_usage[0]["llm_provider_id"] == "p2"

    @pytest.mark.asyncio
    async def test_lookup_failure_keeps_tokens_with_blank_attribution(self):
        state = FakeState()
        ctx, _ = _patch_provider_service(error=RuntimeError("lookup exploded"))
        result = {"llm_usage": [{"input_tokens": 9, "output_tokens": 3}]}
        with ctx:
            await merge_llm_usage_from_result(state, result, "node-1", "p1")

        entry = state.llm_usage[0]
        assert entry["input_tokens"] == 9 and entry["output_tokens"] == 3
        assert entry["provider"] == "" and entry["model"] == ""
        assert entry["llm_provider_id"] == "p1"

    @pytest.mark.asyncio
    async def test_state_failure_never_reaches_the_caller(self):
        state = MagicMock()
        state.add_llm_usage.side_effect = RuntimeError("state is broken")
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            await merge_llm_usage_from_result(state, {"llm_usage": [{"input_tokens": 1}]}, "node-1", "p1")

    @pytest.mark.asyncio
    async def test_non_dict_result_and_entries_are_ignored(self):
        state = FakeState()
        await merge_llm_usage_from_result(state, "not a dict", "node-1", "p1")
        await merge_llm_usage_from_result(state, {"llm_usage": []}, "node-1", "p1")
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            await merge_llm_usage_from_result(state, {"llm_usage": ["junk"]}, "node-1", "p1")
        assert state.llm_usage == []


class TestNodeRequestedCaching:

    @pytest.mark.asyncio
    async def test_the_request_marks_every_entry(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider(), "p2": _provider("Anthropic", "claude-3-opus")})
        result = {"llm_usage": [{"input_tokens": 1}, {"input_tokens": 2, "provider_id": "p2"}]}
        with ctx:
            await merge_llm_usage_from_result(state, result, "node-1", "p1", True)

        assert [e["prompt_caching_enabled"] for e in state.llm_usage] == [True, True]

    @pytest.mark.asyncio
    async def test_without_the_request_a_plain_provider_stays_unmarked(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            await merge_llm_usage_from_result(state, {"llm_usage": [{"input_tokens": 1}]}, "node-1", "p1")

        assert state.llm_usage[0]["prompt_caching_enabled"] is False

    @pytest.mark.asyncio
    async def test_record_node_llm_usage_forwards_the_request(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            await record_node_llm_usage(state, _message({"input_tokens": 5}), "node-1", "p1", None, True)

        assert state.llm_usage[0]["prompt_caching_enabled"] is True


class TestRecordNodeLlmUsage:
    @pytest.mark.asyncio
    async def test_records_usage_with_purpose(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            await record_node_llm_usage(
                state, _message({"input_tokens": 5, "output_tokens": 2}), "node-1", "p1", "smart_route"
            )

        entry = state.llm_usage[0]
        assert entry["input_tokens"] == 5 and entry["purpose"] == "smart_route"

    @pytest.mark.asyncio
    async def test_missing_metadata_still_counts_as_a_call(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            await record_node_llm_usage(state, _message(None), "node-1", "p1", "nlp_classify")

        entry = state.llm_usage[0]
        assert entry["input_tokens"] == 0 and entry["output_tokens"] == 0
        assert entry["token_details"] == {USAGE_METADATA_MISSING: True}

    @pytest.mark.asyncio
    async def test_no_response_records_nothing(self):
        state = FakeState()
        await record_node_llm_usage(state, None, "node-1", "p1")
        assert state.llm_usage == []

    @pytest.mark.asyncio
    async def test_extraction_failure_falls_back_to_a_placeholder(self):
        state = FakeState()
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx, patch(
            "app.modules.workflow.engine.llm_usage_tracking.extract_usage_from_aimessage",
            side_effect=RuntimeError("bad message"),
        ):
            await record_node_llm_usage(state, _message({"input_tokens": 5}), "node-1", "p1")

        assert state.llm_usage[0]["token_details"] == {USAGE_METADATA_MISSING: True}


class TestRecordCompactionUsage:
    @pytest.mark.asyncio
    async def test_pops_the_raw_message_and_records_it(self):
        state = FakeState()
        summary = {"summary": "text", "_llm_response": _message({"input_tokens": 30, "output_tokens": 8})}
        ctx, _ = _patch_provider_service({"p1": _provider()})
        with ctx:
            await record_compaction_usage(state, summary, "node-1", "p1")

        assert "_llm_response" not in summary
        assert state.llm_usage[0]["purpose"] == "compaction"
        assert state.llm_usage[0]["input_tokens"] == 30

    @pytest.mark.asyncio
    async def test_summary_without_a_response_records_nothing(self):
        state = FakeState()
        await record_compaction_usage(state, {"summary": "text"}, "node-1", "p1")
        await record_compaction_usage(state, "not a dict", "node-1", "p1")
        assert state.llm_usage == []
