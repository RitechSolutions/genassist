"""
Chat node implementations using the BaseNode class.
"""

from typing import Any, Dict
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.utils import validate_input_schema

logger = logging.getLogger(__name__)


class ChatInputNode(BaseNode):
    """
    Chat input node that receives user messages.

    This node demonstrates how to implement a simple input node
    using the BaseNode class.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the chat input.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with the message
        """
        # For chat input nodes, get the message from state or config
        input_schema = config.get("inputSchema", {})
        logger.info("ChatInputNode %s processed: %s", self.node_id, input_schema.keys())

        # Validate and get values using the reusable validation function
        try:
            validated_data = validate_input_schema(
                input_schema=input_schema,
                data_getter=self.get_state().get_value,
            )
            self.set_node_input(validated_data)

            return validated_data
        except ValueError as e:
            self.set_node_output({"error": str(e)})
            raise e


class ChatOutputNode(BaseNode):
    """
    Chat output node that formats responses.

    This node demonstrates how to implement an output node
    using the BaseNode class.
    """

    async def process(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:  # pylint: disable=unused-argument
        """
        Process the chat output by forwarding the input from the last connected node.

        Args:
            config: The resolved configuration for the node

        Returns:
            The output from the last connected node
        """
        #source_output = self.get_last_node_output()
        source_output = self.get_input_from_source()
        logger.info(
            "ChatOutputNode %s forwarding output: %s", self.node_id, source_output
        )

        # Simply forward the source output
        return source_output
