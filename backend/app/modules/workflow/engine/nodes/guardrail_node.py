"""
Guardrail node: checks one text with the same detector as the agent's Guardrails policy.
"""

import json
from typing import Any, Dict

from pydantic import ValidationError

from app.modules.workflow.guardrails.detectors import check_text, verdict
from app.modules.workflow.guardrails.turn import previous_reply
from app.schemas.guardrails import GuardrailChecks

from ..base_node import BaseNode
from ..guardrail_exits import GuardrailExitMixin


class GuardrailNode(GuardrailExitMixin, BaseNode):
    """Routes the text to Passed, or the blocked message to Blocked."""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        raw = config.get("text")
        text = raw if isinstance(raw, str) else ("" if raw is None else json.dumps(raw, default=str))
        self.set_node_input({"text": text})
        state = self.get_state()
        # Fields saved empty (a tags field defaults to None) take the policy defaults
        settings = {key: value for key, value in config.items() if value is not None}
        try:
            checks = GuardrailChecks.model_validate({**settings, "judge_provider_id": config.get("providerId")})
        except ValidationError:
            checks = GuardrailChecks()
            verdicts = [
                verdict(
                    "node", "detector_error", "block", "error",
                    category="invalid_settings", detector="rules", source=self.node_id,
                )
            ]
            blocked = False
        else:
            usage: list[dict] = []
            context = await previous_reply(self.get_memory()) if checks.previous_reply_context else None
            verdicts, blocked = await check_text(
                text, checks, "node", "block", usage, source=self.node_id, node_id=self.node_id, context=context
            )
            for entry in usage:
                state.add_llm_usage(**entry)
        state.guardrail_events.extend(verdicts)
        message = checks.blocked_message if blocked else text
        return self.exit_to(not blocked, {"message": message, "guardrail": {"passed": not blocked, "checks": verdicts}})
