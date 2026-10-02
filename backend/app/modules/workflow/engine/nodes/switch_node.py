"""
Switch node implementation using the BaseNode class.

N-way routing that mirrors the Conditional Router's two modes, but selects one
of many cases instead of making a true/false decision:

* Rule mode (default) compares a single value against every case, top to
  bottom; the first match wins.
* Smart Mode asks an LLM to pick one case from the routing prompt, using each
  case's label and value as its description.

Anything that selects no case (no match, missing config, an invalid LLM answer
or an LLM error) takes the default branch.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.dependencies.injector import injector
from app.modules.workflow.llm.provider import LLMProvider

from ..base_node import BaseNode
from ..conditions import evaluate, parse_bool as _parse_bool, to_text as _to_text

logger = logging.getLogger(__name__)

DEFAULT_ROUTE = "default"
DEFAULT_MATCH_MODE = "equal"

DEFAULT_SMART_SWITCH_SYSTEM_PROMPT = (
    "You are a routing decision engine. Choose exactly one route from the list "
    "of routes you are given. Return only the route id. Do not explain. Do not "
    "add extra text."
)


def handle_for_route(route: str) -> str:
    """The source handle a route leaves through (case ``case_1`` -> ``output_case_1``)."""
    return f"output_{route}"


class SwitchNode(BaseNode):
    """
    Switch node that routes workflow execution into one of several branches.

    Each case has an ``id``, a display ``label`` and a ``value``. The node
    selects one case (by rule or, in Smart Mode, by LLM) and follows only the
    edges leaving that case's handle (``output_<case id>``); when no case is
    selected it follows ``output_default``.
    """

    MATCH_MODES = ["equal", "contains", "starts_with", "ends_with", "regex"]

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the switch node and determine the execution path.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with the routing decision and the next nodes to run
        """
        smart_mode_enabled = _parse_bool(config.get("smartModeEnabled", False))
        value = _to_text(config.get("switchValue")).strip()
        match_mode = str(config.get("matchMode") or DEFAULT_MATCH_MODE)
        case_sensitive = _parse_bool(config.get("caseSensitive", False))
        cases = self._normalize_cases(config.get("cases"))

        if smart_mode_enabled:
            system_for_llm = (
                str(config.get("systemPrompt") or "").strip()
                or DEFAULT_SMART_SWITCH_SYSTEM_PROMPT
            )
            matched_case = await self._select_smart_case(
                str(config.get("providerId") or "").strip(),
                str(config.get("smartPrompt") or "").strip(),
                system_for_llm,
                cases,
            )
        else:
            matched_case = self._find_matching_case(value, match_mode, case_sensitive, cases)

        route = matched_case["id"] if matched_case else DEFAULT_ROUTE
        next_nodes = self._get_route_targets(route)

        output = {
            "route": route,
            "label": matched_case["label"] if matched_case else "Default",
            "matched_case": matched_case,
            "value": value,
            "next_nodes": next_nodes,
            "smartModeEnabled": smart_mode_enabled,
            "matchMode": match_mode,
            "caseSensitive": case_sensitive,
        }

        if not next_nodes:
            logger.info("SwitchNode %s route %s has no connected branch", self.node_id, route)
        logger.info("SwitchNode %s routed to %s", self.node_id, route)

        return output

    @staticmethod
    def _normalize_cases(raw: Any) -> List[Dict[str, str]]:
        """Keep well-formed cases only, in their configured order."""
        if not isinstance(raw, list):
            return []
        cases = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            case_id = str(item.get("id") or "").strip()
            if not case_id or case_id == DEFAULT_ROUTE:
                continue
            cases.append(
                {
                    "id": case_id,
                    "label": str(item.get("label") or "").strip() or f"Case {index + 1}",
                    "value": _to_text(item.get("value")),
                }
            )
        return cases

    async def _select_smart_case(
        self,
        provider_id: str,
        smart_prompt: str,
        system_prompt: str,
        cases: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        """Ask the LLM to pick a case; any problem falls back to the default branch."""
        if not provider_id:
            logger.warning("SwitchNode %s Smart Mode: missing providerId, using default route", self.node_id)
            return None
        if not smart_prompt:
            logger.warning("SwitchNode %s Smart Mode: missing smartPrompt, using default route", self.node_id)
            return None
        if not cases:
            logger.warning("SwitchNode %s Smart Mode: no cases configured, using default route", self.node_id)
            return None

        try:
            llm_provider = injector.get(LLMProvider)
            llm_model = await llm_provider.get_model(provider_id)
            response = await llm_model.bind(temperature=0, max_tokens=20).ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=self._build_smart_prompt(smart_prompt, cases)),
                ]
            )
            # Record before interpreting the answer
            from app.modules.workflow.engine.llm_usage_tracking import record_node_llm_usage

            await record_node_llm_usage(self.get_state(), response, self.node_id, provider_id, "smart_switch")

            answer = str(response.content)
        except Exception as e:
            logger.error(
                "SwitchNode %s Smart Mode execution failed: %s; using default route",
                self.node_id,
                e,
            )
            return None

        selected = self._case_from_answer(answer, cases)
        if selected is None:
            logger.info(
                "SwitchNode %s Smart Mode: answer %r selects no case, using default route",
                self.node_id,
                answer,
            )
        return selected

    @staticmethod
    def _build_smart_prompt(smart_prompt: str, cases: List[Dict[str, str]]) -> str:
        """The routing prompt followed by the routes the model may answer with."""
        lines = [smart_prompt, "", "Routes:"]
        for switch_case in cases:
            description = switch_case["value"].strip()
            detail = f"{switch_case['label']} - {description}" if description else switch_case["label"]
            lines.append(f"- {switch_case['id']}: {detail}")
        lines.append(f"- {DEFAULT_ROUTE}: none of the routes above apply")
        lines.append("")
        lines.append("Answer with the route id only.")
        return "\n".join(lines)

    @staticmethod
    def _case_from_answer(answer: str, cases: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Map the model's answer to a case by id, then by label; anything else is no case.

        ``default`` is the reserved fallback route offered in the prompt, so it
        always means "no case", even when a case happens to be labelled "Default".
        """
        normalized = answer.strip().strip("`\"'.").strip().casefold()
        if not normalized or normalized == DEFAULT_ROUTE:
            return None
        for switch_case in cases:
            if switch_case["id"].casefold() == normalized:
                return switch_case
        for switch_case in cases:
            if switch_case["label"].casefold() == normalized:
                return switch_case
        return None

    def _find_matching_case(
        self,
        value: str,
        match_mode: str,
        case_sensitive: bool,
        cases: List[Dict[str, str]],
    ) -> Optional[Dict[str, str]]:
        """The first case whose value matches, or None to take the default branch."""
        if match_mode not in self.MATCH_MODES:
            logger.warning(
                "SwitchNode %s unsupported match mode: %s, using default route",
                self.node_id,
                match_mode,
            )
            return None

        if not value:
            logger.warning("SwitchNode %s has no value to route on, using default route", self.node_id)
            return None

        for switch_case in cases:
            if self._matches(value, match_mode, case_sensitive, switch_case):
                return switch_case
        return None

    def _matches(
        self,
        value: str,
        match_mode: str,
        case_sensitive: bool,
        switch_case: Dict[str, str],
    ) -> bool:
        """Evaluate one case, never raising: a broken case simply does not match."""
        try:
            return evaluate(value, match_mode, switch_case["value"], case_sensitive)
        except re.error as e:
            logger.error(
                "SwitchNode %s invalid regex in case %s: %s",
                self.node_id,
                switch_case["id"],
                e,
            )
            return False

    def _get_route_targets(self, route: str) -> List[str]:
        """Targets of the edges leaving this route's handle.

        Handles are matched exactly (not by substring) so ``output_case_1`` never
        also picks up ``output_case_10``.
        """
        handle = handle_for_route(route)
        source_edges = self.get_state().source_edges or {}
        targets: List[str] = []
        for edge in source_edges.get(self.node_id, []):
            if edge.get("sourceHandle") != handle:
                continue
            target = edge.get("target")
            if target and target not in targets:
                targets.append(target)
        return targets
