from __future__ import annotations

import logging
from typing import Any, Dict, List, Union

from app.modules.workflow.engine.pii_anonymizer import PIIAnonymizer

logger = logging.getLogger(__name__)

_service = PIIAnonymizer()

# History-fetch methods that may exist on concrete nodes
_HISTORY_METHOD_NAMES = ("_get_chat_history_for_agent", "_get_chat_history_for_context")


class PIIAnonymizerMixin:
    """
    Transparent PII masking layer for LLM workflow nodes.

    Apply as the first base class:

        class LLMModelNode(PIIAnonymizerMixin, BaseNode): ...
        class AgentNode(PIIAnonymizerMixin, BaseNode): ...

    Hooks into execute() — not process() — because both concrete nodes define
    their own process(), which would shadow a mixin-level process() in the MRO.
    Instead, this mixin overrides execute() (which neither node defines), wraps
    self.process with a PII-aware version before calling super().execute(), then
    restores it in a finally block.

    When piiMasking is True in the resolved config:
    - Masks PII in userPrompt before the LLM call
    - Masks PII in chat history by wrapping _get_chat_history_for_agent /
      _get_chat_history_for_context at the instance level, so all trimming modes
      are covered transparently without duplicating the history-fetch logic
    - Restores original values in the result

    systemPrompt is intentionally excluded — it is operator-authored.
    The token_map is local to each execute() call and never persisted.
    """

    _PII_FIELDS: tuple[str, ...] = ("userPrompt",)

    async def execute(self, direct_input: Any = None) -> Any:
        original_process = self.process
        # Accumulates token items produced by history masking during process()
        history_token_items: list[dict[str, Any]] = []
        wrapped_attrs: list[str] = []

        # Wrap history-fetch methods so PII in chat history is masked
        # transparently, regardless of trimming mode.  We capture the bound
        # method before shadowing it with an instance attribute so the wrapper
        # can call the original without recursion.
        for attr_name in _HISTORY_METHOD_NAMES:
            if not hasattr(self, attr_name):
                continue
            original_method = getattr(self, attr_name)  # bound to self via class

            def _make_history_wrapper(orig: Any) -> Any:
                async def _pii_history(
                    memory: Any,
                    config: Dict[str, Any],
                    provider_id: str,
                    system_prompt: str,
                    user_prompt: str,
                ) -> Any:
                    history = await orig(memory, config, provider_id, system_prompt, user_prompt)
                    if not config.get("piiMasking"):
                        return history
                    masked, token_map = _mask_history(history)
                    if token_map:
                        history_token_items.extend(token_map.get("items", []))
                    return masked

                return _pii_history

            setattr(self, attr_name, _make_history_wrapper(original_method))
            wrapped_attrs.append(attr_name)

        async def _pii_process(config: Dict[str, Any]) -> Any:
            if not config.get("piiMasking", False):
                return await original_process(config)

            masked_config = dict(config)
            combined_token_map: dict[str, Any] | None = None

            for field_name in self._PII_FIELDS:
                value = config.get(field_name)
                if isinstance(value, str) and value:
                    masked_value, token_map = _service.mask(value)
                    if token_map:
                        masked_config[field_name] = masked_value
                        if combined_token_map is None:
                            combined_token_map = {"items": []}
                        combined_token_map["items"].extend(token_map.get("items", []))

            result = await original_process(masked_config)

            # Merge token items accumulated from history-fetch wrappers
            if history_token_items:
                if combined_token_map is None:
                    combined_token_map = {"items": []}
                combined_token_map["items"].extend(history_token_items)

            if not combined_token_map:
                return result

            return self._unmask_result(result, combined_token_map)

        self.process = _pii_process
        try:
            return await super().execute(direct_input)  # type: ignore[misc]
        finally:
            del self.process  # remove instance attribute, restores class-level method
            for attr in wrapped_attrs:
                try:
                    delattr(self, attr)
                except AttributeError:
                    pass

    def _unmask_result(self, result: Any, token_map: dict[str, Any]) -> Any:
        if isinstance(result, str):
            return _service.unmask(result, token_map)

        if isinstance(result, dict):
            return {
                k: _service.unmask(v, token_map) if isinstance(v, str) else v
                for k, v in result.items()
            }

        logger.warning(
            "PIIAnonymizerMixin._unmask_result: unexpected result type %s, returning without unmasking",
            type(result).__name__,
        )
        return result


def _mask_history(
    history: Union[List[Dict[str, Any]], str],
) -> tuple[Union[List[Dict[str, Any]], str], dict[str, Any]]:
    """
    Mask PII in chat history (list or string format).

    Returns:
        Tuple of (masked_history, combined_token_map)
    """
    combined_token_map: dict[str, Any] = {"items": []}

    if isinstance(history, str):
        if not history:
            return history, {}
        masked, token_map = _service.mask(history)
        if token_map:
            combined_token_map["items"].extend(token_map.get("items", []))
        return masked, combined_token_map if combined_token_map["items"] else {}

    if not history:
        return history, {}

    masked_history = []
    for msg in history:
        masked_msg = dict(msg)
        content = msg.get("content")
        if isinstance(content, str) and content:
            masked_content, token_map = _service.mask(content)
            masked_msg["content"] = masked_content
            if token_map:
                combined_token_map["items"].extend(token_map.get("items", []))
        masked_history.append(masked_msg)

    return masked_history, combined_token_map if combined_token_map["items"] else {}
