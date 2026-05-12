"""
Router node implementation using the BaseNode class.
"""

import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.dependencies.injector import injector
from app.modules.workflow.llm.provider import LLMProvider

from ..base_node import BaseNode

logger = logging.getLogger(__name__)


def _parse_smart_mode_enabled(raw: Any) -> bool:
    """Accept bool or common string forms from UI / JSON without mis-treating str."""
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    if isinstance(raw, (int, float)):
        return raw != 0
    if isinstance(raw, str):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return False


def _normalize_fallback_route(raw: Any) -> str:
    """Only true/false are valid; anything else becomes false."""
    s = str(raw if raw is not None else "").strip().lower()
    return s if s in ("true", "false") else "false"


DEFAULT_SMART_ROUTER_SYSTEM_PROMPT = (
    "You are a routing decision engine. Return only one value: true or false. "
    "Do not explain. Do not add extra text."
)


class RouterNode(BaseNode):
    """
    Router node that routes workflow execution based on conditions.

    This node demonstrates how to implement conditional routing
    using the BaseNode class.
    If the condition is not met, the node will route to the "false" path.
    If the condition is met, the node will route to the "true" path.
    """

    # Supported comparison operations
    COMPARE_OPTIONS = [
        'equal', 'not_equal', 'contains', 'not_contain',
        'starts_with', 'not_starts_with', 'ends_with',
        'not_ends_with', 'regex'
    ]

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the router node and determine the execution path.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with routing decision and input data
        """
        smart_mode_enabled = _parse_smart_mode_enabled(
            config.get("smartModeEnabled", False)
        )
        fallback_route = _normalize_fallback_route(
            config.get("fallbackRoute", "false")
        )
        provider_id = config.get("providerId") or ""
        smart_prompt = config.get("smartPrompt") or ""
        system_prompt_raw = config.get("systemPrompt")

        first_value = config.get("first_value")
        compare_condition = config.get("compare_condition")
        second_value = config.get("second_value")

        if smart_mode_enabled:
            system_for_llm = (
                (system_prompt_raw or "").strip()
                or DEFAULT_SMART_ROUTER_SYSTEM_PROMPT
            )
            route = await self._evaluate_smart_route(
                str(provider_id).strip(),
                str(smart_prompt).strip(),
                system_for_llm,
                fallback_route,
            )
        else:
            # Determine route based on configuration (unchanged behavior)
            if not all([first_value, compare_condition, second_value]):
                logger.warning(
                    "RouterNode %s missing configuration values", self.node_id
                )
                route = "false"
            else:
                route = self._evaluate_condition(
                    first_value, compare_condition, second_value
                )

        next_nodes = self.get_connected_nodes(route)

        output = {
            "route": route,
            "next_nodes": next_nodes,
            "first_value": first_value,
            "compare_condition": compare_condition,
            "second_value": second_value,
            "smartModeEnabled": smart_mode_enabled,
            "fallbackRoute": fallback_route,
        }

        logger.info("RouterNode %s routed to %s", self.node_id, route)

        return output

    async def _evaluate_smart_route(
        self,
        provider_id: str,
        smart_prompt: str,
        system_prompt: str,
        fallback_route: str,
    ) -> str:
        fb = _normalize_fallback_route(fallback_route)

        if not provider_id:
            logger.warning(
                "RouterNode %s Smart Mode: missing providerId, using fallbackRoute=%s",
                self.node_id,
                fb,
            )
            return fb
        if not smart_prompt:
            logger.warning(
                "RouterNode %s Smart Mode: missing smartPrompt, using fallbackRoute=%s",
                self.node_id,
                fb,
            )
            return fb

        try:
            llm_provider = injector.get(LLMProvider)
            llm_model = await llm_provider.get_model(provider_id)
            response = await llm_model.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=smart_prompt),
                ]
            )
            normalized = str(response.content).strip().lower()
        except Exception as e:
            logger.error(
                "RouterNode %s Smart Mode execution failed: %s; using fallbackRoute=%s",
                self.node_id,
                e,
                fb,
            )
            return fb

        if normalized not in ("true", "false"):
            logger.warning(
                "RouterNode %s Smart Mode: invalid route %r, using fallbackRoute=%s",
                self.node_id,
                normalized,
                fb,
            )
            return fb

        return normalized

    def _evaluate_condition(self,
                            first_value: str,
                            compare_condition: str,
                            second_value: str) -> str:
        """
        Evaluate the routing condition.

        Args:
            input_text: The input text to evaluate
            compare_condition: The comparison operation
            value_condition: The value to compare against
            path_name: The path name for the route

        Returns:
            The selected route path
        """
        if compare_condition not in self.COMPARE_OPTIONS:
            logger.warning(
                f"RouterNode {self.node_id} unsupported condition: {compare_condition}")
            return "message_default"

        try:
            if compare_condition == 'equal':
                route = "true" if first_value == second_value else 'false'
            elif compare_condition == 'not_equal':
                route = "true" if first_value != second_value else 'false'
            elif compare_condition == 'contains':
                route = "true" if second_value in first_value else 'false'
            elif compare_condition == 'not_contain':
                route = "true" if second_value not in first_value else 'false'
            elif compare_condition == 'starts_with':
                route = "true" if first_value.startswith(
                    second_value) else 'false'
            elif compare_condition == 'not_starts_with':
                route = "true" if not first_value.startswith(
                    second_value) else 'false'
            elif compare_condition == 'ends_with':
                route = "true" if first_value.endswith(
                    second_value) else 'false'
            elif compare_condition == 'not_ends_with':
                route = "true" if not first_value.endswith(
                    second_value) else 'false'
            elif compare_condition == 'regex':
                route = "true" if re.search(
                    second_value, first_value) else 'false'
            else:
                route = "false"

        except Exception as e:
            logger.error(
                f"RouterNode {self.node_id} error evaluating condition: {e}")
            route = "false"

        return route
