from typing import Dict, Any
import json
import logging
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr
import importlib
from app.core.utils.string_utils import replace_template_vars
from app.modules.agents.workflow.base_processor import NodeProcessor

logger = logging.getLogger(__name__)

class PythonFunctionNodeProcessor(NodeProcessor):
    """Processor for Python code tool nodes"""

    def _execute_python_code(self, code: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Python code in a controlled environment"""
        # Capture stdout and stderr
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        try:
            # Create a namespace for the code to execute in
            namespace = {
                "params": params,
                "result": None,
                "logger": logger,
                # Add commonly used libraries
                "json": importlib.import_module("json"),
                "requests": importlib.import_module("requests"),
                "datetime": importlib.import_module("datetime"),
                "math": importlib.import_module("math"),
                "re": importlib.import_module("re"),
            }
            
            # Execute the code with redirected output
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, namespace)
            
            # Get the result from the namespace if available
            result = namespace.get("result")
            
            # Construct the response
            output = stdout_buffer.getvalue()
            errors = stderr_buffer.getvalue()
            
            response = {
                "status": 200,
                "data": {
                    "result": result,
                    "output": output,
                    "errors": errors
                }
            }
            
            return response
            
        except Exception as e:
            # Capture any errors during execution
            error_traceback = traceback.format_exc()
            logger.error(f"Error in Python code execution: {str(e)}\n{error_traceback}")
            
            # Get any output that was captured before the error
            output = stdout_buffer.getvalue()
            errors = stderr_buffer.getvalue()
            
            return {
                "status": 500,
                "data": {
                    "error": str(e),
                    "traceback": error_traceback,
                    "output": output,
                    "errors": errors
                }
            }

    async def process(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a Python code tool node with dynamic parameter replacement"""
        # Get base configuration
        node_config = self.get_node_config()
        logger.info(f"input_data config: {input_data}")
        # Get input data
        edge_inputs = await self.get_process_input(input_data)
        user_metadata = self.get_state().get_session_metadata() if self.get_state() else {}

        # Merge all inputs
        input_object = {
            **edge_inputs,  # Edge-based inputs
            **user_metadata  # Session data
        }
        logger.info(f"Input object: {input_object}")
        self.set_input(input_object)
        
        # Get the Python code from the node configuration
        code = node_config.get("code", "")
        if not code:
            error_msg = "No Python code specified for Python tool"
            logger.error(error_msg)
            self.output = {
                "status": 400,
                "data": {"error": error_msg}
            }
            return self.output

        try:
            # Process dynamic values in the code using template variables
            code = replace_template_vars(code, input_object)
            
            # Log the processed code for debugging
            logger.debug(f"Processed Python code:")
            logger.debug(code)
            
            # Execute the Python code
            response = self._execute_python_code(code, input_object)
            self.save_output(response)
            return response
            
        except Exception as e:
            error_msg = f"Error processing Python tool: {str(e)}"
            logger.error(error_msg)
            self.output = {
                "status": 500,
                "data": {"error": error_msg}
            }
            return self.output 