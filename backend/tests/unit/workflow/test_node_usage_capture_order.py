"""Nodes that post-process an LLM answer must record its usage first"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes import router_node as router_module
from app.modules.workflow.engine.nodes import sql_node as sql_module
from app.modules.workflow.engine.nodes.router_node import RouterNode
from app.modules.workflow.engine.nodes.sql_node import SQLNode


class FakeState:
    def __init__(self):
        self.llm_usage = []

    def add_llm_usage(self, **kwargs):
        self.llm_usage.append(kwargs)


def _answer(content, input_tokens=12, output_tokens=3):
    return SimpleNamespace(
        content=content,
        usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens},
        response_metadata={},
    )


def _patch_llm(module, response=None, error=None):
    model = MagicMock()
    model.ainvoke = AsyncMock(return_value=response, side_effect=error)
    model.bind = MagicMock(return_value=model)
    provider = MagicMock()
    provider.get_model = AsyncMock(return_value=model)
    inj = MagicMock()
    inj.get = MagicMock(return_value=provider)
    return patch.object(module, "injector", inj), model


def _patch_provider_lookup(provider="openai", model="gpt-4o"):
    service = MagicMock()
    service.get_by_id = AsyncMock(return_value=SimpleNamespace(llm_model_provider=provider, llm_model=model))
    inj = MagicMock()
    inj.get = MagicMock(return_value=service)
    return patch("app.dependencies.injector.injector", inj)


class TestRouterSmartModeCapture:
    @pytest.mark.asyncio
    async def test_invalid_route_answer_still_records_usage(self):
        state = FakeState()
        node = RouterNode("r1", {"type": "routerNode", "data": {}}, state)
        llm_ctx, _ = _patch_llm(router_module, response=_answer("maybe"))

        with llm_ctx, _patch_provider_lookup():
            route = await node._evaluate_smart_route("p1", "is it x?", "system", "false")

        assert route == "false"
        assert state.llm_usage[0]["purpose"] == "smart_route"
        assert state.llm_usage[0]["input_tokens"] == 12

    @pytest.mark.asyncio
    async def test_unreadable_content_still_records_usage(self):
        state = FakeState()
        node = RouterNode("r1", {"type": "routerNode", "data": {}}, state)

        class Exploding:
            usage_metadata = {"input_tokens": 8, "output_tokens": 1}
            response_metadata = {}

            @property
            def content(self):
                raise RuntimeError("content unavailable")

        llm_ctx, _ = _patch_llm(router_module, response=Exploding())

        with llm_ctx, _patch_provider_lookup():
            route = await node._evaluate_smart_route("p1", "is it x?", "system", "true")

        assert route == "true"
        assert state.llm_usage[0]["input_tokens"] == 8

    @pytest.mark.asyncio
    async def test_valid_route_is_returned_and_recorded_once(self):
        state = FakeState()
        node = RouterNode("r1", {"type": "routerNode", "data": {}}, state)
        llm_ctx, _ = _patch_llm(router_module, response=_answer("TRUE"))

        with llm_ctx, _patch_provider_lookup():
            route = await node._evaluate_smart_route("p1", "is it x?", "system", "false")

        assert route == "true"
        assert len(state.llm_usage) == 1


class TestSqlTranslationCapture:
    @staticmethod
    def _node(state):
        config = {"type": "sqlNode", "data": {}}
        return SQLNode("s1", config, state)

    @staticmethod
    def _config():
        return {
            "mode": "humanQuery",
            "dataSourceId": "ds-1",
            "humanQuery": "how many users?",
            "providerId": "p1",
            "systemPrompt": "",
        }

    @pytest.mark.asyncio
    async def test_translation_failure_after_the_call_keeps_usage(self):
        state = FakeState()
        node = self._node(state)
        llm_ctx, _ = _patch_llm(sql_module)

        async def _translate(_manager, **kwargs):
            kwargs["usage_out"].append(_answer("SELECT 1", input_tokens=40, output_tokens=9))
            raise ValueError("model returned malformed JSON")

        db_manager = MagicMock()
        with llm_ctx, _patch_provider_lookup(), patch.object(
            sql_module.db_provider_manager, "get_database_manager", AsyncMock(return_value=db_manager)
        ), patch.object(sql_module, "translate_to_query", _translate):
            result = await node.process(self._config())

        assert is_node_failure(result)
        assert state.llm_usage[0]["purpose"] == "sql_translate"
        assert state.llm_usage[0]["input_tokens"] == 40

    @pytest.mark.asyncio
    async def test_successful_translation_records_once(self):
        state = FakeState()
        node = self._node(state)
        llm_ctx, _ = _patch_llm(sql_module)

        async def _translate(_manager, **kwargs):
            kwargs["usage_out"].append(_answer("SELECT 1"))
            return {"formatted_query": "SELECT 1"}

        db_manager = MagicMock()
        db_manager.execute_query = AsyncMock(return_value=([{"n": 1}], None))
        with llm_ctx, _patch_provider_lookup(), patch.object(
            sql_module.db_provider_manager, "get_database_manager", AsyncMock(return_value=db_manager)
        ), patch.object(sql_module, "translate_to_query", _translate):
            result = await node.process(self._config())

        assert result["status"] == 200
        assert len(state.llm_usage) == 1
