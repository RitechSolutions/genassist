"""
Unified NLP node implementation using the BaseNode class.

A single node that performs one of several lightweight LLM-backed text-analysis
tasks selected via the ``task`` config value:

- ``classify``: classify text into one (or several) configured categories.
- ``sentiment``: detect sentiment + urgency and a numeric score.
- ``extract``: extract requested fields/entities as structured JSON.
- ``summarize``: summarize text in a configurable style and length.

Every returned dict includes a ``"task"`` key and a human-readable ``"message"``
key. On any failure a safe per-task fallback dict with an ``"error"`` note is
returned so downstream nodes always receive a well-formed shape.
"""

import json
import logging
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from app.dependencies.injector import injector
from app.modules.workflow.llm.provider import LLMProvider

from ..base_node import BaseNode
from .nlp_base import parse_json_object

logger = logging.getLogger(__name__)

_STYLE_INSTRUCTIONS = {
    "concise": "Write a concise prose summary.",
    "bullets": "Write the summary as a short list of bullet points.",
    "detailed": "Write a detailed, thorough summary.",
}


def _normalize_categories(raw: Any) -> List[str]:
    """Accept categories as a list or a comma-separated string."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [c.strip() for c in raw.split(",") if c.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(c).strip() for c in raw if str(c).strip()]
    return []


class NLPNode(BaseNode):
    """Unified text-analysis node dispatching on a configured ``task``."""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run the configured NLP task against the input text.

        Args:
            config: The resolved configuration for the node.

        Returns:
            A task-specific dict, always containing ``"task"`` and ``"message"``.
            On failure, the task's safe fallback with an ``"error"`` note.
        """
        task = str(config.get("task", "classify") or "classify")
        provider_id = str(config.get("providerId") or "").strip()
        input_text = str(config.get("inputField", "") or "")

        if task == "sentiment":
            return await self._run_sentiment(config, provider_id, input_text)
        if task == "extract":
            return await self._run_extract(config, provider_id, input_text)
        if task == "summarize":
            return await self._run_summarize(config, provider_id, input_text)
        return await self._run_classify(config, provider_id, input_text)

    async def _run_classify(
        self, config: Dict[str, Any], provider_id: str, input_text: str
    ) -> Dict[str, Any]:
        multi_label = bool(config.get("multiLabel", False))
        categories = _normalize_categories(config.get("categories"))

        if multi_label:
            safe_fallback: Dict[str, Any] = {"task": "classify", "labels": [], "message": ""}
        else:
            safe_fallback = {"task": "classify", "label": "", "confidence": 0.0, "message": ""}

        if not provider_id or not categories or not input_text:
            logger.warning("NLPNode %s (classify) missing providerId/categories/input", self.node_id)
            return {**safe_fallback, "error": "Missing providerId, categories or input"}

        category_list = ", ".join(categories)
        if multi_label:
            system_prompt = (
                "You are a text classification engine. Classify the user's text into "
                f"one or more of exactly these categories: {category_list}. "
                'Return STRICT JSON only, no prose, in the form '
                '{"labels": [{"label": "<category>", "confidence": <0.0-1.0>}]}. '
                "Only use the provided categories."
            )
        else:
            system_prompt = (
                "You are a text classification engine. Classify the user's text into "
                f"exactly one of these categories: {category_list}. "
                'Return STRICT JSON only, no prose, in the form '
                '{"label": "<category>", "confidence": <0.0-1.0>}. '
                "Only use one of the provided categories."
            )

        try:
            llm = await injector.get(LLMProvider).get_model(provider_id)
            response = await llm.bind(temperature=0).ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=input_text),
                ]
            )
            parsed = parse_json_object(str(response.content))
        except Exception as e:  # pylint: disable=broad-except
            logger.error("NLPNode %s (classify) LLM execution failed: %s", self.node_id, e)
            return {**safe_fallback, "error": str(e)}

        if not parsed:
            logger.warning("NLPNode %s (classify) could not parse LLM output", self.node_id)
            return {**safe_fallback, "error": "Could not parse classification output"}

        if multi_label:
            labels = parsed.get("labels") or []
            if not isinstance(labels, list):
                labels = []
            label_names = [str(item.get("label", "")) for item in labels if isinstance(item, dict)]
            return {
                "task": "classify",
                "labels": labels,
                "message": ", ".join([n for n in label_names if n]),
            }

        label = str(parsed.get("label", "") or "")
        confidence = parsed.get("confidence", 0.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        return {"task": "classify", "label": label, "confidence": confidence, "message": label}

    async def _run_sentiment(
        self, config: Dict[str, Any], provider_id: str, input_text: str
    ) -> Dict[str, Any]:
        scale = config.get("scale") or "1-5"

        safe_fallback: Dict[str, Any] = {
            "task": "sentiment",
            "sentiment": "neutral",
            "urgency": "low",
            "score": 0,
            "message": "",
        }

        if not provider_id or not input_text:
            logger.warning("NLPNode %s (sentiment) missing providerId/input", self.node_id)
            return {**safe_fallback, "error": "Missing providerId or input"}

        system_prompt = (
            "You are a sentiment and urgency analysis engine. Analyze the user's text "
            "and return STRICT JSON only, no prose, in the form "
            '{"sentiment": "positive|neutral|negative", '
            '"urgency": "low|medium|high", '
            f'"score": <number on a {scale} scale>}}. '
            f"The score must be a number within the {scale} range reflecting urgency."
        )

        try:
            llm = await injector.get(LLMProvider).get_model(provider_id)
            response = await llm.bind(temperature=0).ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=input_text),
                ]
            )
            parsed = parse_json_object(str(response.content))
        except Exception as e:  # pylint: disable=broad-except
            logger.error("NLPNode %s (sentiment) LLM execution failed: %s", self.node_id, e)
            return {**safe_fallback, "error": str(e)}

        if not parsed:
            logger.warning("NLPNode %s (sentiment) could not parse LLM output", self.node_id)
            return {**safe_fallback, "error": "Could not parse analysis output"}

        sentiment = str(parsed.get("sentiment", "neutral") or "neutral")
        urgency = str(parsed.get("urgency", "low") or "low")
        score = parsed.get("score", 0)

        return {
            "task": "sentiment",
            "sentiment": sentiment,
            "urgency": urgency,
            "score": score,
            "message": f"{sentiment} / urgency: {urgency}",
        }

    async def _run_extract(
        self, config: Dict[str, Any], provider_id: str, input_text: str
    ) -> Dict[str, Any]:
        schema_spec = str(config.get("schema", "") or "").strip()

        safe_fallback: Dict[str, Any] = {"task": "extract", "entities": {}, "message": ""}

        if not provider_id or not schema_spec or not input_text:
            logger.warning("NLPNode %s (extract) missing providerId/schema/input", self.node_id)
            return {**safe_fallback, "error": "Missing providerId, schema or input"}

        system_prompt = (
            "You are an entity extraction engine. Extract the requested fields from "
            "the user's text. The requested fields are described as follows: "
            f"{schema_spec}. "
            "Return STRICT JSON only, no prose, as a single object whose keys are "
            "exactly the requested field names. Use null for any field that is not "
            "present in the text."
        )

        try:
            llm = await injector.get(LLMProvider).get_model(provider_id)
            response = await llm.bind(temperature=0).ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=input_text),
                ]
            )
            parsed = parse_json_object(str(response.content))
        except Exception as e:  # pylint: disable=broad-except
            logger.error("NLPNode %s (extract) LLM execution failed: %s", self.node_id, e)
            return {**safe_fallback, "error": str(e)}

        if parsed is None:
            logger.warning("NLPNode %s (extract) could not parse LLM output", self.node_id)
            return {**safe_fallback, "error": "Could not parse extraction output"}

        # Extracted fields are namespaced under ``entities`` (reachable downstream
        # via ``{{source.entities.<field>}}``) and deliberately NOT spread at the
        # top level, so a user-configured field name can never collide with an
        # engine-reserved output key such as ``next_nodes``.
        extracted = parsed
        return {
            "task": "extract",
            "entities": extracted,
            "message": json.dumps(extracted),
        }

    async def _run_summarize(
        self, config: Dict[str, Any], provider_id: str, input_text: str
    ) -> Dict[str, Any]:
        style = config.get("style") or "concise"
        max_length = config.get("maxLength", 200)
        try:
            max_length = int(max_length)
        except (TypeError, ValueError):
            max_length = 200

        safe_fallback: Dict[str, Any] = {"task": "summarize", "summary": "", "message": ""}

        if not provider_id or not input_text:
            logger.warning("NLPNode %s (summarize) missing providerId/input", self.node_id)
            return {**safe_fallback, "error": "Missing providerId or input"}

        style_instruction = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["concise"])
        system_prompt = (
            "You are a summarization engine. Summarize the user's text. "
            f"{style_instruction} "
            f"Keep the summary within approximately {max_length} words. "
            "Return only the summary text with no preamble."
        )

        try:
            llm = await injector.get(LLMProvider).get_model(provider_id)
            response = await llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=input_text),
                ]
            )
            summary = str(response.content).strip()
        except Exception as e:  # pylint: disable=broad-except
            logger.error("NLPNode %s (summarize) LLM execution failed: %s", self.node_id, e)
            return {**safe_fallback, "error": str(e)}

        return {"task": "summarize", "summary": summary, "message": summary}
