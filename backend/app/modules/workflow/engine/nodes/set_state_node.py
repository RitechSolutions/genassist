"""
Set state node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging

from ..base_node import BaseNode

logger = logging.getLogger(__name__)


class SetStateNode(BaseNode):
    """
    Set state node that updates stateful parameter values in Redis and session.

    Configuration:
    {
        "name": string,
        "states": [
            {
                "key": string,    # Stateful parameter name
                "value": string    # Value to set (can contain {{variables}})
            }
        ]
    }
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the set state node by updating stateful values in Redis and session.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with the updated states
        """
        states = config.get("states", [])

        if not states:
            logger.warning("SetStateNode %s has no states to update", self.node_id)
            return {"updated": [], "error": "No states configured"}

        memory = self.get_memory()
        session = self.get_state().get_session()
        updated_states = {}

        try:
            for state_config in states:
                key = state_config.get("key")
                value = state_config.get("value")

                if not key:
                    logger.warning("SetStateNode %s: state config missing key", self.node_id)
                    continue

                # Value is already resolved by BaseNode.execute() via replace_config_vars
                # So {{variables}} have already been replaced with actual values

                # Update Redis
                await memory.set_stateful_value(key, value)

                # Update session
                session[key] = value
                self.get_state().update_session_value(key, value)

                updated_states[key] = value
                logger.debug(
                    "SetStateNode %s updated stateful value: %s = %s",
                    self.node_id, key, value
                )

            logger.info(
                "SetStateNode %s successfully updated %d stateful values",
                self.node_id, len(updated_states)
            )

            return {
                "status": "success",
                "updated": updated_states,
                "count": len(updated_states)
            }

        except Exception as e:  # pylint: disable=broad-except
            error_msg = f"Error updating stateful values: {str(e)}"
            logger.error(f"SetStateNode {self.node_id}: {error_msg}", exc_info=True)
            return {
                "status": "error",
                "error": error_msg,
                "updated": updated_states
            }
