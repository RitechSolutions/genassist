"""
Router node implementation using the BaseNode class.
"""

from typing import Any, Dict
import logging
import re

from ..base_node import BaseNode

logger = logging.getLogger(__name__)


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

        # Get routing configuration from resolved config
        first_value = config.get("first_value")
        compare_condition = config.get("compare_condition")
        second_value = config.get("second_value")

        # Determine route based on configuration
        if not all([first_value, compare_condition, second_value]):
            logger.warning(
                f"RouterNode {self.node_id} missing configuration values")
            route = "false"
        else:
            route = self._evaluate_condition(
                first_value, compare_condition, second_value
            )

        next_nodes = self.get_connected_nodes(route)

        # Create output with routing decision
        output = {
            "route": route,
            "next_nodes": next_nodes,
            "first_value": first_value,
            "compare_condition": compare_condition,
            "second_value": second_value

        }

        logger.info(f"RouterNode {self.node_id} routed to {route}")

        return output

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
