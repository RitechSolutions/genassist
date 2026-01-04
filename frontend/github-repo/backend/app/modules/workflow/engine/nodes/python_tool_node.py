"""
Python tool node implementation using the BaseNode class.
"""

from typing import Dict, Any
import logging

from app.modules.workflow.engine.base_node import BaseNode
from app.modules.workflow.utils import execute_python_code

logger = logging.getLogger(__name__)


class PythonToolNode(BaseNode):
    """Python code tool node using the BaseNode approach"""

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a Python code tool node with dynamic parameter replacement.

        Args:
            config: The resolved configuration for the node

        Returns:
            Dictionary with Python code execution results
        """
        # Get configuration values (already resolved by BaseNode)
        code = config.get("code", "")
        unwrap = config.get("unwrap", False)

        # Validate code
        if not code:
            error_msg = "No Python code specified for Python tool"
            logger.error(error_msg)
            return {
                "status": 400,
                "data": {"error": error_msg}
            }

        self.set_node_input(code)

        try:
            # Execute the Python code
            response = await execute_python_code(code, {})
            if unwrap:
                response = response.get("result", None)
            return response

        except Exception as e:
            error_msg = f"Error processing Python tool: {str(e)}"
            logger.error(error_msg)
            return {
                "status": 500,
                "data": {"error": error_msg}
            }
