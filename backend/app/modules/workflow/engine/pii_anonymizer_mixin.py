from __future__ import annotations

import logging
from typing import Any, Dict

from app.modules.workflow.engine.pii_anonymizer import PIIAnonymizer

logger = logging.getLogger(__name__)

_service = PIIAnonymizer()


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
    - Restores original values in the result

    systemPrompt is intentionally excluded — it is operator-authored.
    The token_map is local to each execute() call and never persisted.
    """

    _PII_FIELDS: tuple[str, ...] = ("userPrompt",)

    async def execute(self, direct_input: Any = None) -> Any:
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
                        masked_config[field_name] = masked_value
                        if combined_token_map is None:
                            combined_token_map = {"items": []}
                        combined_token_map["items"].extend(token_map.get("items", []))

            result = await original_process(masked_config)

            if not combined_token_map:
                return result

            return self._unmask_result(result, combined_token_map)

        self.process = _pii_process
        try:
            return await super().execute(direct_input)  # type: ignore[misc]
        finally:
            del self.process  # remove instance attribute, restores class-level method

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
