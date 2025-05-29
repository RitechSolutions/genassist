from typing import Protocol, Any, Dict
import logging
import requests
import importlib.util
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr
import json

from langchain_core.tools import BaseTool,StructuredTool 
from pydantic import BaseModel, Field, create_model
from typing import Dict, Any, List, Type, Callable
from typing import Callable, Any
from pydantic import BaseModel, Field, create_model
import inspect
from app.genagent.models.tool import ToolConfig
logger = logging.getLogger(__name__)


class DynamicToolGenerator:
    """Utility class for generating Langchain tools from configuration"""
    @staticmethod
    def create_tool_function(tool_id: str, config: ToolConfig, tool_type: str):
           
        def tool_function(**kwargs: Any) -> str:
            try:
                logger.info(f"Executing {tool_type} tool {tool_id}")
                logger.info(kwargs)                
                if tool_type == "api":
                    return ApiToolImplementation(config).execute(kwargs)
                elif tool_type == "function":
                    return PythonToolImplementation(config).execute(kwargs)
                else:
                    return f"Unsupported tool type: {tool_type}"
            except Exception as e:
                logger.error(f"Error executing tool {tool_id}: {str(e)}")
                return f"Error executing tool: {str(e)}"
            
        return tool_function
        
    
    @staticmethod
    def generate_tool_from_config(tool_config: ToolConfig, tool_function: Callable) -> BaseTool:
        """
        Generate a Langchain tool from a tool configuration.
        
        Args:
            tool_config: The tool configuration dictionary
            tool_function: The callable function to execute when the tool is used
            
        Returns:
            A BaseTool instance configured according to the tool_config
        """
        tool_id = tool_config.id
        tool_name = tool_config.name
        tool_description = tool_config.description
        tool_type = tool_config.type        
        # Generate a prefix based on the tool type
        tool_prefix = "api" if tool_type == "api" else "python"
        formatted_name = f"{tool_prefix}_tool_{tool_id}"
        parameters_schema = tool_config.parameters_schema

        ArgModel = DynamicToolGenerator._create_pydantic_model_from_schema(
            "Parameters", parameters_schema
        )
        # If we have a schema, create a Pydantic model for the tool arguments
      
        return StructuredTool.from_function(
            name=formatted_name,
            description=f"{tool_name}: {tool_description}",
            func=tool_function,
            args_schema=ArgModel,
        )         
           

    
    @staticmethod
    def _create_pydantic_model_from_schema(
        model_name: str, 
        parameters_schema: Dict[str, Dict[str, Any]]
    ) -> Type[BaseModel]:
        """
        Create a Pydantic model from a parameters schema.
        
        Args:
            model_name: Name to use for the model
            parameters_schema: Dictionary of parameter definitions
            {"location": {"type": str, "default": ..., "description": "City name"},
        Returns:
            A dynamically created Pydantic model class
        """
        # Create field definitions
        type_mapping = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        fields = {
            key: (type_mapping[cfg.type], Field(cfg.default, description=cfg.description))
            for key, cfg in parameters_schema.items()
        }
        model_class_name = f"{model_name.capitalize()}Input"
        
        return create_model(model_class_name, **fields)

    @staticmethod
    def generate_tools_from_configs(
        tool_configs: List[ToolConfig], 
        # function_factory: Callable[[str, Dict[str, Any], str], Callable]
    ) -> List[BaseTool]:
        """
        Generate a list of tools from tool configurations.
        
        Args:
            tool_configs: List of tool configuration dictionaries
            function_factory: Factory function to create the tool functions
            
        Returns:
            List of BaseTool instances
        """
        tools = []
        
        
        for config in tool_configs:
            tool_id = config.id
            if not tool_id:
                continue
                
            tool_type = config.type
   
            # Create the function for this tool using the factory
            tool_function = DynamicToolGenerator.create_tool_function(tool_id, config, tool_type)
            
            # Generate the tool
            tool = DynamicToolGenerator.generate_tool_from_config(config, tool_function)
            tools.append(tool)
            
        return tools

class ToolImplementation(Protocol):
    """Protocol defining how tool implementations should behave"""
    def execute(self, params: Any) -> str:
        """Execute a tool with the given parameters"""
        ...



class ApiToolImplementation(ToolImplementation):
    """Implementation of API tools"""
    
    def __init__(self, api_tool_config: ToolConfig):
        """Initialize with the tool service"""
        self.api_tool_config = api_tool_config
    
    def execute(self, params: Dict[str, Any]) -> str:
        """Execute an API tool with the given parameters"""
        logger.info("execute_api_tool")
        tool_id = self.api_tool_config.id
        logger.info(tool_id)
        logger.info(params)
        
        try:

            config = self.api_tool_config.api_config
            # Get the tool definition
         
            if not config:
                return f"Error: Tool configuration not found"
            
            if self.api_tool_config.type != "api":
                return f"Error: Tool with ID {tool_id} is not an API tool"
            
            # Get the API endpoint
            endpoint = config.endpoint
            if not endpoint:
                return f"Error: Tool with ID {tool_id} has no API endpoint defined"
            
            method = config.method
            headers = config.headers
            query_params = config.query_params
            body = config.body

            # Replace placeholders in headers, query_params, and body
            def replace_placeholders(obj):
                if isinstance(obj, dict):
                    return {k: replace_placeholders(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [replace_placeholders(item) for item in obj]
                elif isinstance(obj, str) and obj.startswith('@'):
                    param_name = obj[1:]  # Remove the @ symbol
                    return params.get(param_name, obj)  # Return original if not found
                else:
                    return obj
            
            headers = replace_placeholders(headers)
            query_params = replace_placeholders(query_params)
            body = replace_placeholders(body)
            logger.info(json.dumps(body, indent=2))
            logger.info(json.dumps(headers, indent=2))
            logger.info(json.dumps(query_params, indent=2))
            if method == "GET":
                response = requests.get(endpoint, headers=headers, params=query_params)
            elif method == "POST":
                response = requests.post(endpoint, headers=headers, json=body)
            elif method == "PUT":
                response = requests.put(endpoint, headers=headers, json=body)
            elif method == "DELETE":
                response = requests.delete(endpoint, headers=headers, json=body)
            else:
                return f"Error: Unsupported method: {method}"

            # Make the API call
            logger.info(response.json())
            logger.info("api_tool_response")
            
            # Handle the response
            if response.status_code >= 200 and response.status_code < 300:
                return f"API call successful: {response.text}"
            else:
                logger.error(f"API call failed with status code {response.status_code}: {response.text}")
                return f"API call failed with status code {response.status_code}: {response.text}"
        except Exception as e:
            logger.error(f"Error calling API tool: {str(e)}")
            return f"Error calling API tool: {str(e)}"


class PythonToolImplementation(ToolImplementation):
    """Implementation for executing Python code tools"""
    
    def __init__(self, python_tool_config: ToolConfig):
        """Initialize with the tool configuration"""
        self.python_tool_config = python_tool_config
        
    def execute(self, params: Dict[str, Any]) -> str:
        """Execute a Python code tool with the given parameters"""
        logger.info("execute_python_tool")
        tool_id = self.python_tool_config.id
        logger.info(params)
        
        try:
            config = self.python_tool_config
            # Get the tool definition
            if not config:
                return f"Error: Tool configuration not found"
            
            if config.type != "function":
                return f"Error: Tool with ID {tool_id} is not a Python tool"
            
            # Get the Python code
            code = config.code
            if not code:
                return f"Error: Tool with ID {tool_id} has no Python code defined"
            
            result = self._execute_python_code(code, params)
            print(result)
            # Execute the Python code with the provided parameters
            return result
        except Exception as e:
            logger.error(f"Error executing Python tool: {str(e)}")
            return f"Error executing Python tool: {str(e)}"
    
    def _execute_python_code(self, code: str, params: Dict[str, Any]) -> str:
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
                # Add a timeout mechanism if possible
                exec(code, namespace)
            
            # Get the result from the namespace if available
            result = namespace.get("result")
            
            # Construct the response
            output = stdout_buffer.getvalue()
            errors = stderr_buffer.getvalue()
            
            response_parts = []
            
            # Add the result if available
            if result is not None:
                if isinstance(result, (dict, list, tuple)):
                    import json
                    response_parts.append(f"Result: {json.dumps(result, indent=2)}")
                else:
                    response_parts.append(f"Result: {result}")
            
            # Add stdout if available
            if output:
                response_parts.append(f"Output:\n{output}")
            
            # Add stderr if available
            if errors:
                response_parts.append(f"Errors:\n{errors}")
            
            # Return the combined response or a default message
            if response_parts:
                return "\n\n".join(response_parts)
            else:
                return "Python code executed successfully with no output."
            
        except Exception as e:
            # Capture any errors during execution
            error_traceback = traceback.format_exc()
            logger.error(f"Error in Python code execution: {str(e)}\n{error_traceback}")
            
            # Get any output that was captured before the error
            output = stdout_buffer.getvalue()
            errors = stderr_buffer.getvalue()
            
            error_message = f"Python execution error: {str(e)}"
            
            if output:
                error_message += f"\n\nPartial output:\n{output}"
            
            if errors:
                error_message += f"\n\nErrors:\n{errors}"
                
            return error_message

