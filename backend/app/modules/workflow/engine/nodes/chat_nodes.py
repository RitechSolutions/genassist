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
        logger.debug("ChatInputNode %s processed: %s", self.node_id, input_schema.keys())

        # Validate and get values using the reusable validation function
        try:
            validated_data = validate_input_schema(
                input_schema=input_schema,
                data_getter=self.get_state().get_value,
            )

            session = self.get_state().get_session()
            if "conversation_history" in input_schema:
                conversation_history = session.get("conversation_history", None)
                if conversation_history is None or conversation_history == "":
                    conversation_history = await self.get_memory().get_chat_history(
                        as_string=True
                    )
                    session["conversation_history"] = conversation_history
                    validated_data["conversation_history"] = conversation_history
                    self.get_state().update_session_value(
                        "conversation_history", conversation_history
                    )

            # Handle stateful parameters
            memory = self.get_memory()
            for param_name, param_schema in input_schema.items():
                if param_schema.get("stateful", False):
                    # For stateful parameters, always check Redis first to ensure we have
                    # the latest value (which may have been updated by a sub-workflow)
                    # Then fall back to session if Redis doesn't have it
                    stateful_value = await memory.get_stateful_value(param_name, None)
                    if stateful_value is not None:
                        # Redis has the value, use it and update session
                        session[param_name] = stateful_value
                        validated_data[param_name] = stateful_value
                        self.get_state().update_session_value(param_name, stateful_value)
                    else:
                        # Redis doesn't have it, check session
                        stateful_value = session.get(param_name, None)
                        if stateful_value is None or stateful_value == "":
                            # Not in session either, use default if available
                            if param_schema.get("required", False) is False and "defaultValue" in param_schema:
                                default_value = param_schema["defaultValue"]
                                session[param_name] = default_value
                                validated_data[param_name] = default_value
                                self.get_state().update_session_value(param_name, default_value)
                        else:
                            # Value in session but not in Redis, use session value
                            validated_data[param_name] = stateful_value

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
        # source_output = self.get_last_node_output()
        source_output = self.get_input_from_source()
        logger.debug(
            "ChatOutputNode %s forwarding output: %s", self.node_id, source_output
        )

        # Simply forward the source output
        return source_output
