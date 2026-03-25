"""Unit tests for PIIAnonymizerMixin."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.engine.pii_anonymizer_mixin import PIIAnonymizerMixin


class _FakeBaseNode:
    node_id = "test-node-001"

    async def process(self, config: Dict[str, Any]) -> Any:
        raise NotImplementedError


class _StringNode(PIIAnonymizerMixin, _FakeBaseNode):
    """Mimics LLMModelNode — process() returns str."""

    def __init__(self, return_value: str = "LLM response"):
        self._inner = AsyncMock(return_value=return_value)

    async def process(self, config: Dict[str, Any]) -> str:
        return await self._inner(config)


class _DictNode(PIIAnonymizerMixin, _FakeBaseNode):
    """Mimics AgentNode — process() returns dict."""

    def __init__(self, message: str = "Agent response", steps: list | None = None):
        self._inner = AsyncMock(return_value={"message": message, "steps": steps or []})

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return await self._inner(config)


def _passthrough_mask(text):
    if "alice@example.com" in text:
        token = "<EMAIL_ADDRESS_1>"
        masked = text.replace("alice@example.com", token)
        token_map = {
            "items": [
                {
                    "entity_type": "EMAIL_ADDRESS",
                    "token": token,
                    "original": "alice@example.com",
                }
            ]
        }
        return masked, token_map
    return text, {}


def _passthrough_unmask(text, token_map):
    for item in token_map.get("items", []):
        text = text.replace(item["token"], item["original"])
    return text


class TestDisabledPath:
    @pytest.mark.asyncio
    async def test_passthrough_when_pii_masking_false(self):
        node = _StringNode(return_value="Hello!")
        config = {"piiMasking": False, "userPrompt": "My email is alice@example.com"}

        result = await PIIAnonymizerMixin.process(node, config)

        assert node._inner.call_args[0][0]["userPrompt"] == "My email is alice@example.com"
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_passthrough_when_pii_masking_missing(self):
        node = _StringNode(return_value="Hi!")
        config = {"userPrompt": "test"}

        result = await PIIAnonymizerMixin.process(node, config)

        assert node._inner.call_args[0][0]["userPrompt"] == "test"
        assert result == "Hi!"


class TestEnabledPath:
    @pytest.mark.asyncio
    async def test_user_prompt_is_masked_before_llm(self):
        node = _StringNode(return_value="noted.")
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {"piiMasking": True, "userPrompt": "Contact alice@example.com for info"}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await PIIAnonymizerMixin.process(node, config)

        called_prompt = node._inner.call_args[0][0]["userPrompt"]
        assert "alice@example.com" not in called_prompt
        assert "<EMAIL_ADDRESS_1>" in called_prompt

    @pytest.mark.asyncio
    async def test_system_prompt_is_never_masked(self):
        node = _StringNode(return_value="ok")
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {
            "piiMasking": True,
            "userPrompt": "Hi alice@example.com",
            "systemPrompt": "You are a helpful assistant.",
        }

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await PIIAnonymizerMixin.process(node, config)

        assert node._inner.call_args[0][0]["systemPrompt"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_str_result_is_unmasked(self):
        node = _StringNode(return_value="Email <EMAIL_ADDRESS_1> is on file.")
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {"piiMasking": True, "userPrompt": "My email is alice@example.com"}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            result = await PIIAnonymizerMixin.process(node, config)

        assert "alice@example.com" in result
        assert "<EMAIL_ADDRESS_1>" not in result

    @pytest.mark.asyncio
    async def test_dict_result_message_is_unmasked(self):
        node = _DictNode(message="Hi <EMAIL_ADDRESS_1>!", steps=["step1"])
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {"piiMasking": True, "userPrompt": "reach me at alice@example.com"}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            result = await PIIAnonymizerMixin.process(node, config)

        assert "alice@example.com" in result["message"]
        assert "<EMAIL_ADDRESS_1>" not in result["message"]
        assert result["steps"] == ["step1"]

    @pytest.mark.asyncio
    async def test_no_pii_prompt_skips_unmask(self):
        node = _StringNode(return_value="Fine!")
        mock_service = MagicMock()
        mock_service.mask.return_value = ("What is 2+2?", {})

        config = {"piiMasking": True, "userPrompt": "What is 2+2?"}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            result = await PIIAnonymizerMixin.process(node, config)

        mock_service.unmask.assert_not_called()
        assert result == "Fine!"

    @pytest.mark.asyncio
    async def test_original_config_not_mutated(self):
        node = _StringNode(return_value="ok")
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.return_value = "ok"

        original_prompt = "Contact alice@example.com"
        config = {"piiMasking": True, "userPrompt": original_prompt}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await PIIAnonymizerMixin.process(node, config)

        assert config["userPrompt"] == original_prompt

    @pytest.mark.asyncio
    async def test_empty_user_prompt_skips_masking(self):
        node = _StringNode(return_value="ok")
        mock_service = MagicMock()

        config = {"piiMasking": True, "userPrompt": ""}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await PIIAnonymizerMixin.process(node, config)

        mock_service.mask.assert_not_called()
