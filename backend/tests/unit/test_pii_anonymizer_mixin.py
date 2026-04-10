"""Unit tests for PIIAnonymizerMixin."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.engine.pii_anonymizer_mixin import PIIAnonymizerMixin


class _FakeBaseNode:
    node_id = "test-node-001"

    async def execute(self, direct_input: Any = None) -> Any:
        """Base execute that calls process with resolved config."""
        # Config should be stored on the instance before execute is called
        return await self.process(getattr(self, "_test_config", {}))

    async def process(self, config: Dict[str, Any]) -> Any:
        raise NotImplementedError


class _StringNode(PIIAnonymizerMixin, _FakeBaseNode):
    """Mimics LLMModelNode — process() returns str."""

    def __init__(self, return_value: str = "LLM response"):
        self._inner = AsyncMock(return_value=return_value)
        self._test_config: Dict[str, Any] = {}

    async def process(self, config: Dict[str, Any]) -> str:
        return await self._inner(config)

    async def run_with_config(self, config: Dict[str, Any]) -> str:
        """Helper to run execute with the given config."""
        self._test_config = config
        return await self.execute()


class _DictNode(PIIAnonymizerMixin, _FakeBaseNode):
    """Mimics AgentNode — process() returns dict."""

    def __init__(self, message: str = "Agent response", steps: list | None = None):
        self._inner = AsyncMock(return_value={"message": message, "steps": steps or []})
        self._test_config: Dict[str, Any] = {}

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return await self._inner(config)

    async def run_with_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to run execute with the given config."""
        self._test_config = config
        return await self.execute()


def _passthrough_mask(text):
    if "alice@example.com" in text:
        token = "johndoe1@example.com"
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

        result = await node.run_with_config(config)

        assert node._inner.call_args[0][0]["userPrompt"] == "My email is alice@example.com"
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_passthrough_when_pii_masking_missing(self):
        node = _StringNode(return_value="Hi!")
        config = {"userPrompt": "test"}

        result = await node.run_with_config(config)

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
            await node.run_with_config(config)

        called_prompt = node._inner.call_args[0][0]["userPrompt"]
        assert "alice@example.com" not in called_prompt
        assert "johndoe1@example.com" in called_prompt

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
            await node.run_with_config(config)

        assert node._inner.call_args[0][0]["systemPrompt"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_str_result_is_unmasked(self):
        node = _StringNode(return_value="Email johndoe1@example.com is on file.")
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {"piiMasking": True, "userPrompt": "My email is alice@example.com"}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            result = await node.run_with_config(config)

        assert "alice@example.com" in result
        assert "johndoe1@example.com" not in result

    @pytest.mark.asyncio
    async def test_dict_result_message_is_unmasked(self):
        node = _DictNode(message="Hi johndoe1@example.com!", steps=["step1"])
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {"piiMasking": True, "userPrompt": "reach me at alice@example.com"}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            result = await node.run_with_config(config)

        assert "alice@example.com" in result["message"]
        assert "johndoe1@example.com" not in result["message"]
        assert result["steps"] == ["step1"]

    @pytest.mark.asyncio
    async def test_no_pii_prompt_skips_unmask(self):
        node = _StringNode(return_value="Fine!")
        mock_service = MagicMock()
        mock_service.mask.return_value = ("What is 2+2?", {})

        config = {"piiMasking": True, "userPrompt": "What is 2+2?"}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            result = await node.run_with_config(config)

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
            await node.run_with_config(config)

        assert config["userPrompt"] == original_prompt

    @pytest.mark.asyncio
    async def test_empty_user_prompt_skips_masking(self):
        node = _StringNode(return_value="ok")
        mock_service = MagicMock()

        config = {"piiMasking": True, "userPrompt": ""}

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await node.run_with_config(config)

        mock_service.mask.assert_not_called()


class _MockMemory:
    """Mock conversation memory for testing chat history masking."""

    def __init__(self, messages: list | None = None, history_string: str = ""):
        self._messages = messages or []
        self._history_string = history_string

    async def get_messages(self, max_messages: int = 10) -> list:
        return self._messages[-max_messages:]

    async def get_chat_history(self, as_string: bool = False, max_messages: int = 10) -> str | list:
        if as_string:
            return self._history_string
        return self._messages[-max_messages:]


class _AgentStyleNode(PIIAnonymizerMixin, _FakeBaseNode):
    """Mimics AgentNode — defines _get_chat_history_for_agent (list format)."""

    def __init__(self, memory: _MockMemory | None = None):
        self._inner = AsyncMock(return_value={"message": "Agent response", "steps": []})
        self._memory = memory
        self._test_config: Dict[str, Any] = {}
        self._last_chat_history: Any = None

    async def _get_chat_history_for_agent(
        self, memory: Any, config: Dict[str, Any], provider_id: str, system_prompt: str, user_prompt: str
    ) -> list:
        max_messages = config.get("maxMessages", 10)
        return await memory.get_messages(max_messages=max_messages)

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate what AgentNode does: call the (possibly wrapped) history method
        if config.get("memory") and self._memory:
            self._last_chat_history = await self._get_chat_history_for_agent(
                self._memory, config, "provider", "system", "user"
            )
        return await self._inner(config)

    async def run_with_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to run execute with the given config."""
        self._test_config = config
        return await self.execute()


class _LLMStyleNode(PIIAnonymizerMixin, _FakeBaseNode):
    """Mimics LLMModelNode — defines _get_chat_history_for_context (string format)."""

    def __init__(self, memory: _MockMemory | None = None):
        self._inner = AsyncMock(return_value="LLM response")
        self._memory = memory
        self._test_config: Dict[str, Any] = {}
        self._last_chat_history: Any = None

    async def _get_chat_history_for_context(
        self, memory: Any, config: Dict[str, Any], provider_id: str, system_prompt: str, user_prompt: str
    ) -> str:
        max_messages = config.get("maxMessages", 10)
        return await memory.get_chat_history(as_string=True, max_messages=max_messages)

    async def process(self, config: Dict[str, Any]) -> str:
        # Simulate what LLMModelNode does: call the (possibly wrapped) history method
        if config.get("memory") and self._memory:
            self._last_chat_history = await self._get_chat_history_for_context(
                self._memory, config, "provider", "system", "user"
            )
        return await self._inner(config)

    async def run_with_config(self, config: Dict[str, Any]) -> str:
        """Helper to run execute with the given config."""
        self._test_config = config
        return await self.execute()


class TestChatHistoryMasking:
    """Tests for chat history PII masking."""

    @pytest.mark.asyncio
    async def test_masks_list_format_chat_history(self):
        """AgentNode style: masks PII in list-format chat history."""
        messages = [
            {"role": "user", "content": "Contact me at alice@example.com"},
            {"role": "assistant", "content": "I'll note that email."},
        ]
        memory = _MockMemory(messages=messages)
        node = _AgentStyleNode(memory=memory)
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {
            "piiMasking": True,
            "memory": True,
            "memoryTrimmingMode": "message_count",
            "maxMessages": 10,
            "userPrompt": "Hello",
        }

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await node.run_with_config(config)

        assert node._last_chat_history is not None
        assert isinstance(node._last_chat_history, list)
        assert "johndoe1@example.com" in node._last_chat_history[0]["content"]
        assert "alice@example.com" not in node._last_chat_history[0]["content"]

    @pytest.mark.asyncio
    async def test_masks_string_format_chat_history(self):
        """LLMModelNode style: masks PII in string-format chat history."""
        history_str = "User: Contact me at alice@example.com\nAssistant: Noted."
        memory = _MockMemory(history_string=history_str)
        node = _LLMStyleNode(memory=memory)
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {
            "piiMasking": True,
            "memory": True,
            "memoryTrimmingMode": "message_count",
            "maxMessages": 10,
            "userPrompt": "Hello",
        }

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await node.run_with_config(config)

        assert node._last_chat_history is not None
        assert isinstance(node._last_chat_history, str)
        assert "johndoe1@example.com" in node._last_chat_history
        assert "alice@example.com" not in node._last_chat_history

    @pytest.mark.asyncio
    async def test_combines_token_maps_from_prompt_and_history(self):
        """Token maps from userPrompt and chat history are combined for unmasking."""
        messages = [{"role": "user", "content": "Contact alice@example.com"}]
        memory = _MockMemory(messages=messages)
        node = _AgentStyleNode(memory=memory)

        def multi_mask(text):
            if "alice@example.com" in text:
                token = "johndoe1@example.com"
                masked = text.replace("alice@example.com", token)
                return masked, {"items": [{"entity_type": "EMAIL_ADDRESS", "token": token, "original": "alice@example.com"}]}
            if "bob@test.com" in text:
                token = "johndoe2@example.com"
                masked = text.replace("bob@test.com", token)
                return masked, {"items": [{"entity_type": "EMAIL_ADDRESS", "token": token, "original": "bob@test.com"}]}
            return text, {}

        mock_service = MagicMock()
        mock_service.mask.side_effect = multi_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        # Response contains both tokens
        node._inner.return_value = {"message": "johndoe1@example.com and johndoe2@example.com", "steps": []}

        config = {
            "piiMasking": True,
            "memory": True,
            "memoryTrimmingMode": "message_count",
            "maxMessages": 10,
            "userPrompt": "Also reach bob@test.com",
        }

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            result = await node.run_with_config(config)

        # Both emails should be unmasked in result
        assert "alice@example.com" in result["message"]
        assert "bob@test.com" in result["message"]

    @pytest.mark.asyncio
    async def test_skips_history_masking_when_memory_disabled(self):
        """No chat history masking when memory is disabled."""
        node = _AgentStyleNode()
        mock_service = MagicMock()
        mock_service.mask.side_effect = _passthrough_mask
        mock_service.unmask.side_effect = _passthrough_unmask

        config = {
            "piiMasking": True,
            "memory": False,
            "userPrompt": "Hello alice@example.com",
        }

        with patch("app.modules.workflow.engine.pii_anonymizer_mixin._service", mock_service):
            await node.run_with_config(config)

        # History method was never called because memory is disabled
        assert node._last_chat_history is None


