"""
Guardrail provenance node implementation using the BaseNode class.
"""

import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.dependencies.injector import injector
from app.modules.workflow.llm.provider import LLMProvider

from ..base_node import BaseNode

logger = logging.getLogger(__name__)


class GuardrailProvenanceNode(BaseNode):
    """
    Guardrail node that scores how well an answer is supported by a context.

    Config keys (under node.data, after template resolution):
        answer_field:      Answer text to check (string, required).
        context_field:     Context text or concatenated sources (string, required).
        min_score:         Minimum provenance score (0-1) to be considered "pass".
                           Default: 0.5
        fail_on_violation: If True, add `verdict="fail"` and `blocked=True`.
                           If False, just annotate and pass through.
                           Default: False
        use_llm_judge:     If True, use an LLM-as-judge to compute provenance
                           score instead of only the heuristic overlap score.
        llm_provider_id:   Optional LLM provider ID for the judge. If omitted,
                           the default provider is used.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a provenance check between answer and context."""
        # Read configuration (already resolved by BaseNode)
        min_score = float(config.get("min_score", 0.5))
        fail_on_violation = bool(config.get("fail_on_violation", False))
        fallback_answer_enabled = bool(config.get("fallback_answer_enabled", False))
        fallback_answer = config.get("fallback_answer") or ""
        provenance_mode = config.get("provenance_mode")
        use_llm_judge = bool(config.get("use_llm_judge", False) or provenance_mode == "llm")
        llm_provider_id = config.get("llm_provider_id")

        # After BaseNode.replace_config_vars, config values are already resolved, so we
        # treat them as the final answer/context texts.
        answer = config.get("answer_field") or ""
        context_text = config.get("context_field") or ""

        if not isinstance(answer, str):
            answer = str(answer)
        if not isinstance(context_text, str):
            context_text = str(context_text)

        # Track node input in state for debugging/inspection
        self.set_node_input({"answer": answer, "context": context_text})

        # Start with heuristic score as a baseline
        heuristic_score = self._naive_provenance_score(answer, context_text)
        score = heuristic_score
        judge_details: Dict[str, Any] | None = None

        # Optionally call an LLM-as-judge to refine provenance score
        if use_llm_judge:
            try:
                llm_judge_system_prompt_suffix = config.get("llm_judge_system_prompt_suffix", "") or ""
                llm_score, judge_details = await self._run_llm_judge(
                    answer=answer,
                    context=context_text,
                    provider_id=llm_provider_id,
                    system_prompt_suffix=llm_judge_system_prompt_suffix,
                )
                # Prefer the LLM score when available
                if llm_score is not None:
                    score = llm_score
            except Exception as exc:  # pylint: disable=broad-except
                logger.error(
                    "GuardrailProvenanceNode %s: LLM judge failed: %s",
                    self.node_id,
                    exc,
                )

        passed = score >= min_score
        verdict = "pass" if passed else "fail"

        guardrail_result: Dict[str, Any] = {
            "type": "provenance",
            "score": score,
            "threshold": min_score,
            "verdict": verdict,
            "heuristic_score": heuristic_score,
        }
        if judge_details is not None:
            guardrail_result["llm_judge"] = judge_details

        logger.info(
            "GuardrailProvenanceNode %s: score=%.3f threshold=%.3f verdict=%s",
            self.node_id,
            score,
            min_score,
            verdict,
        )

        effective_answer = answer
        if not passed and fallback_answer_enabled and fallback_answer:
            effective_answer = fallback_answer
            guardrail_result["fallback_used"] = True
            logger.info(
                "GuardrailProvenanceNode %s: provenance violation — using fallback answer",
                self.node_id,
            )

        output: Dict[str, Any] = {
            "answer": effective_answer,
            "context": context_text,
            "_guardrail_provenance": guardrail_result,
        }

        if not passed and fail_on_violation and not (fallback_answer_enabled and fallback_answer):
            output["blocked"] = True
            output["verdict"] = "provenance_fail"

        return output

    def _naive_provenance_score(self, answer: str, context: str) -> float:
        """
        Compute a simplistic provenance score based on token overlap.

        This is a placeholder implementation; an LLM-as-judge can be
        enabled via configuration for a stronger signal.
        """
        if not answer or not context:
            return 0.0

        answer_tokens = {t.lower() for t in answer.split() if len(t) > 3}
        context_tokens = {t.lower() for t in context.split() if len(t) > 3}

        if not answer_tokens:
            return 0.0

        overlap = answer_tokens & context_tokens
        return len(overlap) / float(len(answer_tokens))

    async def _run_llm_judge(
        self,
        answer: str,
        context: str,
        provider_id: str | None = None,
        system_prompt_suffix: str = "",
    ) -> tuple[float | None, Dict[str, Any]]:
        """
        Use an LLM-as-judge to estimate provenance.

        Expected JSON response format:
            {
              "verdict": "supported" | "partially_supported" | "unsupported",
              "score": 0.0-1.0,
              "reason": "short explanation"
            }

        system_prompt_suffix is appended after the base instructions but before
        the JSON format requirement, allowing callers to tune judge behaviour
        (e.g. "When no Context is available, treat the answer as supported.")
        without breaking the structured output contract.
        """
        llm_provider = injector.get(LLMProvider)
        llm = await llm_provider.get_model(provider_id)

        base_instructions = (
            "You are a strict provenance judge. Given a CONTEXT and an ANSWER, "
            "decide whether the answer is fully supported by the context, "
            "partially supported, or not supported."
        )

        extra_instructions = (
            f"\n\nAdditional instructions:\n{system_prompt_suffix.strip()}" if system_prompt_suffix.strip() else ""
        )

        json_format_requirement = (
            "\n\nReturn ONLY a compact JSON object in this exact format:\n"
            '{"verdict": "supported|partially_supported|unsupported", '
            '"score": 0.0-1.0, '
            '"reason": "short explanation"}\n'
            "Do not include any extra text or explanation."
        )

        system_prompt = base_instructions + extra_instructions + json_format_requirement

        user_prompt = f"CONTEXT:\n{context}\n\nANSWER:\n{answer}\n"

        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )

        raw_content = getattr(response, "content", "")
        if isinstance(raw_content, list):
            raw_content = " ".join(str(part) for part in raw_content)

        judge_details: Dict[str, Any] = {
            "raw": raw_content,
        }

        try:
            parsed = json.loads(raw_content)
            verdict = str(parsed.get("verdict", "unsupported")).lower()
            score = float(parsed.get("score", 0.0))
            reason = parsed.get("reason", "")

            judge_details.update(
                {
                    "verdict": verdict,
                    "score": score,
                    "reason": reason,
                }
            )

            # Clamp score to [0, 1]
            score = max(0.0, min(1.0, score))
            return score, judge_details

        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "GuardrailProvenanceNode %s: failed to parse LLM judge JSON response '%s': %s",
                self.node_id,
                raw_content,
                exc,
            )
            return None, judge_details
