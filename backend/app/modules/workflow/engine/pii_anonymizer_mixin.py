from __future__ import annotations

import logging
from typing import Any, Dict, List, Union

from app.modules.workflow.engine.pii_anonymizer import PIIAnonymizer

logger = logging.getLogger(__name__)

_service = PIIAnonymizer()

# History-fetch methods that may exist on concrete nodes
_HISTORY_METHOD_NAMES = ("_get_chat_history_for_agent", "_get_chat_history_for_context")


def _wrap_history_method(method_name: str, original_fn: Any) -> Any:
    """
    Wraps a history-fetch method at class-definition time.

    Reads piiMasking from config (same dict the node received) and, when
    enabled, masks PII in the returned history and stores replacements in
    self._pii_history_token_items so execute() can merge them into the
    combined token map for unmasking the final result.
    """

    async def _wrapped(
        self: Any,
        memory: Any,
        config: Dict[str, Any],
        provider_id: str,
        system_prompt: str,
        user_prompt: str,
    ) -> Any:
        history = await original_fn(self, memory, config, provider_id, system_prompt, user_prompt)

        if not config.get("piiMasking"):
            return history

        masked, token_map = _mask_history(history)

        if token_map:
            logger.debug(
                "[PII] %s — history masked, %d replacement(s): %r",
                method_name,
                len(token_map.get("items", [])),
                token_map.get("items", []),
            )
            getattr(self, "_pii_history_token_items", []).extend(token_map.get("items", []))

        return masked

    _wrapped.__name__ = original_fn.__name__
    _wrapped.__qualname__ = original_fn.__qualname__
    return _wrapped


class PIIAnonymizerMixin:
    """
    Transparent PII masking layer for LLM workflow nodes.

    Apply as the first base class:

        class LLMModelNode(PIIAnonymizerMixin, BaseNode): ...
        class AgentNode(PIIAnonymizerMixin, BaseNode): ...

    How it works:
    - __init_subclass__ wraps _get_chat_history_for_agent /
      _get_chat_history_for_context ONCE at class definition time (not per
      execute() call), so there is no dynamic patching at runtime.
    - execute() sets self._pii_history_token_items = [] before calling
      super().execute(), then merges those items with the prompt token map
      to unmask the final result.
    - _pii_process (injected the same way as before) masks _PII_FIELDS
      (userPrompt) before passing config to the real process().

    systemPrompt is intentionally excluded — it is operator-authored.
    The token map is local to each execute() call and never persisted.
    """

    _PII_FIELDS: tuple[str, ...] = ("userPrompt",)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for method_name in _HISTORY_METHOD_NAMES:
            # Only wrap methods defined directly on this subclass, not
            # inherited ones that may already be wrapped.
            if method_name in cls.__dict__:
                original_fn = cls.__dict__[method_name]
                setattr(cls, method_name, _wrap_history_method(method_name, original_fn))

    async def execute(self, direct_input: Any = None) -> Any:
        # Per-execution accumulator read by the class-level history wrappers
        self._pii_history_token_items: list[dict[str, Any]] = []
        # Per-execution accumulator for prompt token items, used by _unmask_for_tool
        self._pii_prompt_token_items: list[dict[str, Any]] = []
        original_process = self.process

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
                        logger.debug(
                            "[PII] %s masked, %d replacement(s): %r",
                            field_name,
                            len(token_map.get("items", [])),
                            token_map.get("items", []),
                        )
                        masked_config[field_name] = masked_value
                        if combined_token_map is None:
                            combined_token_map = {"items": []}
                        combined_token_map["items"].extend(token_map.get("items", []))

            # Store prompt token items so _unmask_for_tool can access them
            # during tool execution (before process() returns).
            self._pii_prompt_token_items = list(
                combined_token_map.get("items", [])
            ) if combined_token_map else []

            result = await original_process(masked_config)

            # Merge token items accumulated by the class-level history wrappers
            if self._pii_history_token_items:
                if combined_token_map is None:
                    combined_token_map = {"items": []}
                combined_token_map["items"].extend(self._pii_history_token_items)

            if not combined_token_map:
                return result

            unmasked = self._unmask_result(result, combined_token_map)
            logger.debug(
                "[PII] unmasked result using %d replacement(s)",
                len(combined_token_map.get("items", [])),
            )
            return unmasked

        self.process = _pii_process
        try:
            return await super().execute(direct_input)  # type: ignore[misc]
        finally:
            del self.process
            del self._pii_history_token_items
            del self._pii_prompt_token_items

    def _unmask_for_tool(self, text: str) -> str:
        """Unmask PII tokens in a string using the current combined token map.

        This is meant to be called during tool execution (inside process())
        so that tools receive original PII values instead of anonymization
        tokens like ``<EMAIL_ADDRESS_1>``.
        """
        items = getattr(self, "_pii_prompt_token_items", []) + getattr(
            self, "_pii_history_token_items", []
        )
        if not items:
            return text
        return _service.unmask(text, {"items": items})

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
