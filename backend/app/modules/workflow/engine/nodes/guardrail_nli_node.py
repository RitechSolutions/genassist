"""
Guardrail NLI fact-checking node implementation using the BaseNode class.
"""

from typing import Any, Dict
import logging

from ..base_node import BaseNode
from .local_nli_model import local_nli_model

logger = logging.getLogger(__name__)


class GuardrailNliNode(BaseNode):
    """
    Guardrail node that estimates whether an answer is supported by evidence.

    Config keys (under node.data, after template resolution):
        answer_field:           Answer text to check (string, required).
        evidence_field:         Evidence/context text to compare against (string, required).
        min_entail_score:       Minimum entailment score (0-1) to be considered "entails".
                                Default: 0.5
        fail_on_contradiction:  If True, mark output as blocked when verdict is "contradicts".
                                Default: False
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run an NLI-style fact-check between answer and evidence using a local model."""
        min_entail_score = float(config.get("min_entail_score", 0.5))
        fail_on_contradiction = bool(config.get("fail_on_contradiction", False))
        fallback_answer_enabled = bool(config.get("fallback_answer_enabled", False))
        fallback_answer = config.get("fallback_answer") or ""

        # After BaseNode.replace_config_vars, config values are already resolved, so we
        # treat them as the final answer/evidence texts.
        answer = config.get("answer_field") or ""
        evidence = config.get("evidence_field") or ""

        if not isinstance(answer, str):
            answer = str(answer)
        if not isinstance(evidence, str):
            evidence = str(evidence)

        # Track node input in state for debugging/inspection
        self.set_node_input({"answer": answer, "evidence": evidence})

        entail_score, contradiction_score, verdict = local_nli_model.score(
            answer=answer,
            evidence=evidence,
            model_name=config.get("nli_model_name"),
        )

        # Apply local thresholding on entailment score
        if verdict == "entails" and entail_score < min_entail_score:
            verdict = "unknown"

        is_contradiction = verdict == "contradicts"

        guardrail_result = {
            "type": "nli",
            "entail_score": entail_score,
            "contradiction_score": contradiction_score,
            "threshold": min_entail_score,
            "verdict": verdict,
        }

        logger.info(
            "GuardrailNliNode %s: entail=%.3f contradict=%.3f "
            "threshold=%.3f verdict=%s",
            self.node_id,
            entail_score,
            contradiction_score,
            min_entail_score,
            verdict,
        )

        effective_answer = answer
        if is_contradiction and fallback_answer_enabled and fallback_answer:
            effective_answer = fallback_answer
            guardrail_result["fallback_used"] = True
            logger.info(
                "GuardrailNliNode %s: contradiction detected — using fallback answer",
                self.node_id,
            )

        output: Dict[str, Any] = {
            "answer": effective_answer,
            "evidence": evidence,
            "_guardrail_nli": guardrail_result,
        }

        if is_contradiction and fail_on_contradiction and not (fallback_answer_enabled and fallback_answer):
            output["blocked"] = True
            output["verdict"] = "nli_contradiction"

        return output

