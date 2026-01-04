import json
import io
import re
import traceback
from contextlib import redirect_stdout, redirect_stderr
import importlib
from typing import Callable, Dict, Any, List, Union
import logging
import asyncio
import concurrent.futures

logger = logging.getLogger(__name__)


def add_executable_function(code: str) -> str:
    """Add an executable function to the code"""
    if "result = executable_function(params)" in code:
        return code

    template_lines = []
    # Try/except block for execution
    template_lines.append("try:")
    template_lines.append(
        "    # Call the executable function with parameters from params['parameters']"
    )
    template_lines.append("    result = executable_function(params)")
    template_lines.append("")
    template_lines.append("except Exception as e:")
    template_lines.append("    # Handle any errors")
    template_lines.append("    import traceback")
    template_lines.append(
        '    errors = f"Error processing parameters: {str(e)}\\n{traceback.format_exc()}"'
    )
    template_lines.append("")
    return code + "\n" + "\n".join(template_lines)


def _execute_python_code_sync(
    code: str, params: Dict[str, Any], wrap_code: bool = True
) -> Dict[str, Any]:
    """Execute Python code in a controlled environment (synchronous version for thread execution)"""
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
            "pandas": importlib.import_module("pandas"),
            "numpy": importlib.import_module("numpy"),
        }
        if wrap_code:
            executable = add_executable_function(code)
        else:
            executable = code

        logger.info(f"Executable code: {executable}")

        # Execute the code with redirected output
        with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
            exec(executable, namespace)

        # Get the result from the namespace if available
        result = namespace.get("result")
        global_errors = namespace.get("errors")
        # Construct the response
        output = stdout_buffer.getvalue()
        errors = stderr_buffer.getvalue()

        if global_errors:
            errors = errors + "\nGlobal errors: " + str(global_errors)
        response = {"result": result, "output": output, "errors": errors}

        return response

    except Exception as e:
        # Capture any errors during execution
        error_traceback = traceback.format_exc()
        logger.error(f"Error in Python code execution: {str(e)}\n{error_traceback}")

        # Get any output that was captured before the error
        output = stdout_buffer.getvalue()
        errors = stderr_buffer.getvalue()

        return {
            "error": str(e),
            "traceback": error_traceback,
            "output": output,
            "errors": errors,
        }


def sanitize_python_code(code: str) -> str:
    """
    Sanitizes a Python code string before execution:
    - Converts JSON keywords (null, true, false) → Python equivalents
    - Removes trailing commas before ] or }
    - Keeps formatting and indentation intact
    """
    if not isinstance(code, str):
        raise ValueError("sanitize_python_code expects a string")

    clean = code

    # Replace JSON literals with Python ones
    clean = re.sub(r"\bnull\b", "None", clean)
    clean = re.sub(r"\btrue\b", "True", clean)
    clean = re.sub(r"\bfalse\b", "False", clean)

    # Remove trailing commas before ] or }
    clean = re.sub(r",(\s*[}\]])", r"\1", clean)

    return clean


async def execute_python_code(
    code: str, params: Dict[str, Any], wrap_code: bool = True
) -> Dict[str, Any]:
    """Execute Python code in a controlled environment asynchronously in a new thread"""
    try:
        code = sanitize_python_code(code)
        # Create a thread pool executor
        loop = asyncio.get_event_loop()

        # Run the synchronous function in a thread pool
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor, _execute_python_code_sync, code, params, wrap_code
            )

        return result
    except Exception as e:
        logger.error(f"Error in async Python code execution: {str(e)}")
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "output": "",
            "errors": "",
        }


def generate_python_function_template(parameters_schema: Dict[str, Any]) -> str:
    """
    Generate a Python function template based on the parameters schema.
    The generated function takes only 'params' as input and extracts/validates variables inside.
    Dotted parameter names are converted to valid Python variable names using underscores.

    Args:
        parameters_schema: A dictionary with parameter definitions

    Returns:
        A Python code template as a string
    """
    import_keyword = "from typing import Optional"
    template_lines = [
        "# Generated Python function template",
        import_keyword,
        "",
        "# Store your result in the 'result' variable",
        "# Import any additional libraries you need",
        "# import json",
        "# import requests",
        "# import datetime",
        "",
    ]

    # Function definition
    template_lines.append("def executable_function(params):")
    template_lines.append("    # Extract parameters with type validation")
    if not parameters_schema:
        template_lines.append("    # No parameters defined in schema")
        template_lines.append("    pass")
    else:
        for param_name, param_info in parameters_schema.items():
            param_type = param_info.get("type", "string")
            description = param_info.get("description", f"Parameter: {param_name}")
            # Convert dotted names to valid Python variable names
            var_name = param_name.replace(".", "_")
            # Add comment with parameter description
            template_lines.append(f"    # {description}")
            # Generate code to extract and validate parameter based on type
            if param_type == "string":
                template_lines.append(
                    f"    {var_name} = params.get('{param_name}', '')"
                )
                template_lines.append(f"    if not isinstance({var_name}, str):")
                template_lines.append(
                    f"        {var_name} = str({var_name}) if {var_name} is not None else ''"
                )
            elif param_type == "number" or param_type == "integer":
                default = "0"
                convert_func = "float" if param_type == "number" else "int"
                template_lines.append(
                    f"    {var_name} = params.get('{param_name}', {default})"
                )
                template_lines.append(f"    if {var_name} is not None:")
                template_lines.append("        try:")
                template_lines.append(
                    f"            {var_name} = {convert_func}({var_name})"
                )
                template_lines.append("        except (ValueError, TypeError):")
                template_lines.append(f"            {var_name} = {default}")
                template_lines.append("    else:")
                template_lines.append(f"        {var_name} = {default}")
            elif param_type == "boolean":
                template_lines.append(
                    f"    {var_name} = params.get('{param_name}', False)"
                )
                template_lines.append(f"    {var_name} = bool({var_name})")
            elif param_type == "array":
                template_lines.append(
                    f"    {var_name} = params.get('{param_name}', [])"
                )
                template_lines.append(f"    if not isinstance({var_name}, list):")
                template_lines.append(
                    f"        {var_name} = [{var_name}] if {var_name} is not None else []"
                )
            elif param_type == "object":
                template_lines.append(
                    f"    {var_name} = params.get('{param_name}', {{}})"
                )
                template_lines.append(f"    if not isinstance({var_name}, dict):")
                template_lines.append(
                    f"        {var_name} = {{}} if {var_name} is None else {var_name}"
                )
            else:
                # Default to string for unknown types
                template_lines.append(
                    f"    {var_name} = params.get('{param_name}', None)"
                )
            template_lines.append("")  # Add blank line between parameters

    # Add example usage section for the extracted parameters
    template_lines.append("    # Your code logic here - example using the parameters:")
    if parameters_schema:
        example_lines = ["    result = {"]
        for param_name in parameters_schema.keys():
            var_name = param_name.replace(".", "_")
            example_lines.append(f"        '{param_name}': {var_name},")
        example_lines.append("    }")
        template_lines.extend(example_lines)
    else:
        template_lines.append(
            "    result = 'Successfully executed function with no parameters'"
        )
    template_lines.append("")
    template_lines.append("    return result")
    template_lines.append("")

    return "\n".join(template_lines)


def validate_params_against_schema(
    params: Dict[str, Any], schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate and enhance parameters against a schema.
    This is a simplified version of the Agent._validate_params_against_schema method.

    Args:
        params: The parameters to validate
        schema: The parameters schema definition

    Returns:
        The validated and enhanced parameters
    """
    if not schema:
        return params

    result_params: Dict[str, str | int | float | bool | list | dict | None] = {}

    # Apply defaults and type conversions based on schema
    for param_name, param_info in schema.items():
        param_type = str(param_info.get("type", "string"))

        # If parameter is provided, process it
        if param_name in params:
            value = params[param_name]

            # Apply type conversion if needed
            if param_type == "string" and not isinstance(value, str):
                result_params[param_name] = str(value) if value is not None else ""
            elif param_type == "number" and not isinstance(value, (int, float)):
                try:
                    result_params[param_name] = float(value)
                except (ValueError, TypeError):
                    result_params[param_name] = 0
            elif param_type == "integer" and not isinstance(value, int):
                try:
                    result_params[param_name] = int(float(value))
                except (ValueError, TypeError):
                    result_params[param_name] = 0
            elif param_type == "boolean" and not isinstance(value, bool):
                result_params[param_name] = bool(value)
            elif param_type == "array" and not isinstance(value, list):
                result_params[param_name] = [value] if value is not None else []
            elif param_type == "object" and not isinstance(value, dict):
                result_params[param_name] = {} if value is None else value
            else:
                result_params[param_name] = value
        else:
            # Parameter not provided, use default based on type
            if param_type == "string":
                result_params[param_name] = ""
            elif param_type in ["number", "integer"]:
                result_params[param_name] = 0
            elif param_type == "boolean":
                result_params[param_name] = False
            elif param_type == "array":
                result_params[param_name] = []
            elif param_type == "object":
                result_params[param_name] = {}
            else:
                result_params[param_name] = None

    # Include any extra parameters not in the schema
    for param_name, value in params.items():
        if param_name not in result_params:
            result_params[param_name] = value

    return result_params


def create_tool_description(tool: Dict[str, Any], index: int) -> str:
    """Create a description for a specific tool"""
    # Basic information for all tools
    description = [
        f"Tool {index+1}: {tool['name']}",
        f"Type: {tool['type'].replace('Node', '')}",
        f"Description: {tool['description']}",
    ]

    # Add tool-specific details
    if tool["type"] == "apiToolNode":
        description.extend(
            [f"API Endpoint: {tool['endpoint']}", f"Method: {tool['method']}"]
        )
    elif tool["type"] in ["knowledgeToolNode", "knowledgeBaseNode"]:
        description.append(
            f"Knowledge bases: {len(tool.get('selectedBases', []))} selected"
        )

    # Add input parameters
    input_params = []
    for param_name, param_info in tool.get("inputSchema", {}).items():
        if "session." in param_name:
            continue
        required = "required" if param_info.get("required", False) else "optional"
        param_desc = param_info.get("description", "")
        param_type = param_info.get("type", "any")
        input_params.append(
            f"  - {param_name}: {param_type} ({required}){' - ' + param_desc if param_desc else ''}"
        )

    if input_params:
        description.append("Required Parameters:")
        description.extend(input_params)

    # Add output information if available
    output_params = []
    for param_name, param_info in tool.get("outputSchema", {}).items():
        output_params.append(f"  - {param_name}: {param_info.get('type', 'any')}")

    if output_params:
        description.append("Output Schema:")
        description.extend(output_params)

    return "\n".join(description)


def create_tool_selection_prompt(user_input: str, tools: List[Dict[str, Any]]) -> str:
    """Create a prompt for the agent to select appropriate tools and extract required parameters"""
    # Create descriptions for each tool
    tool_descriptions = [
        create_tool_description(tool, i) for i, tool in enumerate(tools)
    ]
    tools_description = "\n\n".join(tool_descriptions)

    return f"""You are an AI assistant that can help users by selecting and using appropriate tools.
                Available tools:

                {tools_description}

                User request: {user_input}

                Please analyze the user's request and determine which tool(s) would be most appropriate to use.
                For each selected tool, extract the required parameters from the user's request.

                Respond in JSON format with the following structure:
                {{
                    "selected_tools": [
                        {{
                            "tool_index": <index of the tool (1-based)>,
                            "reason": "<explanation of why this tool is appropriate>",
                            "extracted_parameters": {{
                                "<parameter_name>": <extracted_value>,
                                ...
                            }},
                            "missing_parameters": [
                                "<list of required parameters that couldn't be extracted>"
                            ]
                        }}
                    ],
                    "should_execute": <true/false>,
                    "explanation": "<explanation of your decision>"
                }}

                Important:
                1. Only select tools where you can extract all required parameters from the user's request
                2. If a tool requires parameters that aren't in the user's request, list them in missing_parameters
                3. For each selected tool, provide the extracted parameters in the format expected by the tool's input schema
                4. If no tool can be used with the available information, set should_execute to false and explain why
                5. For knowledge tools, you should extract a 'query' parameter from the user's request
                6. For API tools, extract parameters matching the input schema or API endpoint requirements"""


def create_direct_response_prompt(prompt: str) -> str:
    """Create a prompt for the agent to provide a direct and informative response to the user's request"""
    return f"""You are a helpful AI assistant. Please provide a clear and helpful response to the following user request:

    User request: {prompt}

    Please provide a direct and informative response that addresses the user's request."""


def create_json_human_prompt(prompt: str, results: Dict[str, Any]) -> str:
    """Create a prompt for the agent to format tool execution results into a clear, natural response for the user"""
    return f"""You are a helpful AI assistant. Please format the following tool execution results into a clear, natural response for the user.

    Original user request: {prompt}

    Tool execution results:
    {json.dumps(results, indent=2)}

    Please provide a natural, conversational response that incorporates the results in a helpful way. Do not mention the tools or technical details unless necessary. Focus on answering the user's request in a clear and helpful manner."""


def map_tool_to_schema(node: Dict[str, Any]) -> Dict[str, Any]:
    """Get list of available tools from connected nodes"""
    node_type = str(node.get("type", ""))
    tool_data = node.get("data", {})

    # Skip non-tool nodes

    # Create a standardized tool representation
    tool = {
        "node_id": node.get("id"),
        "type": node_type,
        "name": tool_data.get("name", f"Unnamed {node_type.replace('Node', '')}"),
        "description": tool_data.get("description", ""),
        "inputSchema": tool_data.get("inputSchema", {}),
        "outputSchema": tool_data.get("outputSchema", {}),
    }
    if node_type not in ["apiToolNode", "knowledgeToolNode", "knowledgeBaseNode"]:
        return tool
    # Add tool-specific properties
    if node_type == "apiToolNode":
        tool.update(
            {
                "endpoint": tool_data.get("endpoint", ""),
                "method": tool_data.get("method", "GET"),
                "parameters": tool_data.get("parameters", {}),
            }
        )
    elif node_type in ["knowledgeToolNode", "knowledgeBaseNode"]:
        tool.update(
            {
                "selectedBases": tool_data.get("selectedBases", []),
                "query_type": "semantic search",
            }
        )

    return tool


def process_path_based_input_data(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process path-based input data to create initial context values for workflow state.

    This function handles dot notation paths in input_data keys and converts them
    to nested structures that can be used to initialize WorkflowState.

    Args:
        input_data: Dictionary with potential dot notation keys (e.g., "metadata.time": 20)
        metadata: Additional metadata dictionary

    Returns:
        Dictionary with processed initial values for WorkflowState
    """
    initial_values = {}

    # Process input_data for path-based keys
    for key, value in input_data.items():
        if "." in key:
            # This is a path-based key, add it to initial_values
            initial_values[key] = value
        else:
            # Regular key, keep as is
            initial_values[key] = value

    return initial_values


def format_dict_for_llm(
    data: dict, format_type: str = "structured", max_depth: int = 10
) -> str:
    """
    Format a dictionary as a string suitable for LLM content consumption.

    Args:
        data: Dictionary to format
        format_type: Type of formatting to apply:
            - "json_pretty": Pretty-printed JSON (default)
            - "json_compact": Compact JSON
            - "structured": Human-readable structured format
            - "key_value": Simple key-value pairs
            - "markdown": Markdown-formatted table/list
        max_depth: Maximum depth for nested structures (to prevent overly long outputs)

    Returns:
        Formatted string representation of the dictionary
    """
    if not isinstance(data, dict):
        return str(data)

    def truncate_nested(obj, current_depth=0):
        """Truncate deeply nested structures to prevent overly long outputs"""
        if current_depth >= max_depth:
            if isinstance(obj, dict):
                return f"<dict with {len(obj)} keys>"
            elif isinstance(obj, list):
                return f"<list with {len(obj)} items>"
            else:
                return str(obj)

        if isinstance(obj, dict):
            return {k: truncate_nested(v, current_depth + 1) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [truncate_nested(item, current_depth + 1) for item in obj]
        else:
            return obj

    # Truncate deeply nested structures
    truncated_data = truncate_nested(data)

    if format_type == "json_pretty":
        return json.dumps(truncated_data, indent=2, ensure_ascii=False, default=str)

    elif format_type == "json_compact":
        return json.dumps(truncated_data, ensure_ascii=False, default=str)

    elif format_type == "structured":

        def format_value(value, indent_level=0):
            indent = "  " * indent_level
            if isinstance(value, dict):
                if not value:
                    return "{}"
                result = "{\n"
                for k, v in value.items():
                    result += f"{indent}  {k}: {format_value(v, indent_level + 1)}\n"
                result += f"{indent}}}"
                return result
            elif isinstance(value, list):
                if not value:
                    return "[]"
                if len(value) == 1:
                    return f"[{format_value(value[0], indent_level)}]"
                result = "[\n"
                for item in value:
                    result += f"{indent}  - {format_value(item, indent_level + 1)}\n"
                result += f"{indent}]"
                return result
            else:
                return str(value)

        return format_value(truncated_data)

    elif format_type == "key_value":

        def flatten_for_kv(obj, parent_key="", separator="."):
            items = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_key = f"{parent_key}{separator}{k}" if parent_key else k
                    if isinstance(v, (dict, list)) and v:
                        items.extend(flatten_for_kv(v, new_key, separator))
                    else:
                        items.append(f"{new_key}: {v}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_key = f"{parent_key}[{i}]"
                    if isinstance(item, (dict, list)) and item:
                        items.extend(flatten_for_kv(item, new_key, separator))
                    else:
                        items.append(f"{new_key}: {item}")
            return items

        items = flatten_for_kv(truncated_data)
        return "\n".join(items)

    elif format_type == "markdown":

        def dict_to_markdown(obj, level=0):
            if isinstance(obj, dict):
                result = ""
                for key, value in obj.items():
                    if isinstance(value, dict):
                        result += f"{'#' * (level + 1)} {key}\n\n"
                        result += dict_to_markdown(value, level + 1)
                    elif isinstance(value, list):
                        result += f"{'#' * (level + 1)} {key}\n\n"
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                result += f"{i + 1}. \n"
                                for k, v in item.items():
                                    result += f"   - **{k}**: {v}\n"
                            else:
                                result += f"{i + 1}. {item}\n"
                        result += "\n"
                    else:
                        result += f"- **{key}**: {value}\n"
                if level == 0:
                    result += "\n"
                return result
            else:
                return str(obj)

        return dict_to_markdown(truncated_data)

    else:
        # Default to pretty JSON
        return json.dumps(truncated_data, indent=2, ensure_ascii=False, default=str)


def validate_input_schema(
    input_schema: Dict[str, Any],
    data_getter: Union[Dict[str, Any], Callable[[str], Any]],
) -> Dict[str, Any]:
    """
    Validate input data against an inputSchema.

    Args:
        input_schema: Schema definition with keys, types, required flags, and defaultValues
        data_getter: Either a dictionary of values or a callable that takes a key and returns a value

    Returns:
        Dictionary with validated values, including defaultValues where applicable

    Raises:
        ValueError: If required fields are missing or types don't match
    """
    validated_data = {}
    type_mapping = {
        "string": "str",
        "number": ("int", "float"),
        "integer": "int",
        "boolean": "bool",
        "array": ("list", "tuple"),
        "object": "dict",
    }

    # Helper to get value from data_getter
    def get_value(key: str) -> Any:
        if isinstance(data_getter, dict):
            return data_getter.get(key)
        return data_getter(key)

    for key, schema_info in input_schema.items():
        value = get_value(key)

        # Check if field is required and value is None
        if schema_info.get("required", False) and value is None:
            error_message = f"value missing for required key: {key}"
            raise ValueError(error_message)

        # Use defaultValue if not required and value is None
        if not schema_info.get("required", False) and value is None:
            if "defaultValue" in schema_info:
                value = schema_info["defaultValue"]

        # Validate type if value is not None
        if value is not None:
            expected_type = schema_info.get("type")
            if expected_type:
                actual_type = type(value).__name__
                expected_python_type = type_mapping.get(expected_type, expected_type)

                if isinstance(expected_python_type, tuple):
                    if actual_type not in expected_python_type:
                        error_message = f"type mismatch for key {key}: expected {expected_type}, got {actual_type}"
                        raise ValueError(error_message)
                elif actual_type != expected_python_type:
                    error_message = f"type mismatch for key {key}: expected {expected_type}, got {actual_type}"
                    raise ValueError(error_message)

        validated_data[key] = value

    return validated_data
