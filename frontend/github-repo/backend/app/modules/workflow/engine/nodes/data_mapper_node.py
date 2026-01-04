"""
Data mapper node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging

from ..base_node import BaseNode
from app.modules.workflow.utils import execute_python_code

logger = logging.getLogger(__name__)


class DataMapperNode(BaseNode):
    """Data mapper node that transforms data between different formats using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a data mapper node with the configured Python script.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with transformed data or error information
        """
        # Get configuration values (already resolved by BaseNode)
        python_script = config.get("pythonScript", "")

        if not python_script:
            logger.warning("No Python script configured for data mapper")
            # Return empty result if no script
            return {"error": "No Python script configured for data mapper"}

        try:
            # Execute the Python script
            response = await execute_python_code(python_script, params={})

            return response

        except Exception as e:
            error_msg = f"Error processing data mapper: {str(e)}"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "input": python_script
            }
