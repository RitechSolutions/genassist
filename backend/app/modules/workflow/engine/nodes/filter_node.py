"""
Filter node implementation using the BaseNode class.

A gate: the branch continues only while a condition holds. It compares one
field against a value with the same comparisons as the Switch node, plus number
comparisons and empty/not-empty checks (see engine/conditions.py).

* Condition true: the node is transparent. It forwards its own input unchanged,
  so downstream nodes read ``{{source...}}`` exactly as if the Filter were not
  there, and every connected node runs.
* Condition false (or a broken condition): the branch stops. If the Filter stops
  the main chat path, its optional ``stopMessage`` becomes the reply, because the
  last node that ran provides the workflow's response.
"""

import logging
import re
from typing import Any, Dict

from ..base_node import BaseNode
from ..conditions import PRESENCE_OPERATORS, evaluate, parse_bool, to_text

logger = logging.getLogger(__name__)

DEFAULT_OPERATOR = "equal"


class FilterNode(BaseNode):
    """Filter node: lets execution continue only when its condition is true."""

    async def process(self, config: Dict[str, Any]) -> Any:
        """
        Evaluate the condition and either pass the input through or stop the branch.

        Args:
            config: The resolved configuration for the node

        Returns:
            The unchanged input when the condition holds; otherwise a stop result
            with ``next_nodes: []`` so the engine runs nothing downstream.
        """
        field = to_text(config.get("field"))
        operator = str(config.get("operator") or DEFAULT_OPERATOR)
        expected = to_text(config.get("value"))
        case_sensitive = parse_bool(config.get("caseSensitive", False))

        passed = self._condition_holds(field, operator, expected, case_sensitive)
        logger.info("FilterNode %s %s", self.node_id, "passed" if passed else "stopped the branch")

        if passed:
            upstream = self.get_input_from_source()
            if upstream is None:
                # Nothing to forward (e.g. tested on its own): report the decision.
                return self._decision(True, field, operator, expected)
            if isinstance(upstream, dict) and "next_nodes" in upstream:
                # The input came from a routing node; its branch choice must not
                # steer what runs after the Filter.
                return {key: value for key, value in upstream.items() if key != "next_nodes"}
            return upstream

        return {
            "message": str(config.get("stopMessage") or "").strip(),
            **self._decision(False, field, operator, expected),
            "next_nodes": [],
        }

    def _condition_holds(self, field: str, operator: str, expected: str, case_sensitive: bool) -> bool:
        """Evaluate the condition, failing closed: a broken condition stops the branch."""
        if operator not in PRESENCE_OPERATORS and not field.strip():
            logger.warning("FilterNode %s has no field to check, stopping the branch", self.node_id)
            return False
        try:
            return evaluate(field, operator, expected, case_sensitive)
        except ValueError as e:
            logger.warning("FilterNode %s %s, stopping the branch", self.node_id, e)
        except re.error as e:
            logger.error("FilterNode %s invalid regex: %s, stopping the branch", self.node_id, e)
        return False

    @staticmethod
    def _decision(passed: bool, field: str, operator: str, expected: str) -> Dict[str, Any]:
        return {
            "passed": passed,
            "field": field.strip(),
            "operator": operator,
            "value": expected.strip(),
        }
