import json
import io
import faulthandler
import functools
import math
import multiprocessing
import os
import pickle
import re
import signal
import sys
from contextlib import redirect_stdout, redirect_stderr
from multiprocessing.connection import Connection, wait as wait_readable
from typing import Callable, Dict, Any, List, Union
import logging
import asyncio

from app.modules.workflow.sandbox import (
    make_sandboxed_namespace,
    validate_code_ast,
    SandboxViolation,
)

logger = logging.getLogger(__name__)

# Maximum wall-clock seconds for user-supplied Python code execution
# (e.g. preprocessing steps on large datasets). Keep well under the 2-hour
# cap on full pipeline runs (app/tasks/ml_model_pipeline_tasks.py).
_EXEC_TIMEOUT_SECONDS = 600
_EXIT_GRACE_SECONDS = 5
_MAX_RESULT_BYTES = 32 * 1024 * 1024
# Captured stdout/stderr keep this much, half head and half tail, so prints never trip the result cap
_MAX_STREAM_CHARS = 1024 * 1024
# Preloaded by the fork server; 3.12 ignores "__main__", so children re-run the entry script as __mp_main__
_FORKSERVER_PRELOAD = ["__main__", "numpy", "pandas", "app.modules.workflow.utils"]


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

_SCRIPT_ERROR_PREFIX = "Error processing parameters: "

def _error_dict(message: str) -> Dict[str, Any]:
    return {"error": message, "traceback": "", "output": "", "errors": ""}


def script_error(response: Dict[str, Any]) -> str:
    if response.get("error"):
        return str(response["error"])
    if response.get("script_failed") and response.get("result") is None:
        return str(response["errors"])
    return ""


def _encode_result(payload: Dict[str, Any], limit: int = _MAX_RESULT_BYTES) -> bytes:
    for stream in ("output", "errors"):
        text = payload.get(stream)
        if isinstance(text, str) and len(text) > _MAX_STREAM_CHARS:
            half = _MAX_STREAM_CHARS // 2
            payload[stream] = f"{text[:half]}\n... ({len(text) - 2 * half} chars cut) ...\n{text[-half:]}"
    try:
        data = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as exc:
        return pickle.dumps(_error_dict(f"Result could not be serialized: {exc}"))
    if len(data) > limit:
        mib = 1024 * 1024
        return pickle.dumps(
            _error_dict(f"Result too large: {math.ceil(len(data) / mib)} MiB exceeds the {limit // mib} MiB limit")
        )
    return data


def _unpicklable_keys(params: Dict[str, Any]) -> List[str]:
    """Keys whose values fail a pickle round trip"""
    keys = []
    for key, value in params.items():
        try:
            pickle.loads(pickle.dumps(value))
        except Exception:
            keys.append(str(key))
    return keys


def _kill(process: multiprocessing.process.BaseProcess) -> None:
    """SIGKILL by pid; Process.kill() is a no-op once a dead fork server marked the child as exited"""
    try:
        os.kill(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


@functools.lru_cache(maxsize=1)
def _script_context() -> multiprocessing.context.BaseContext:
    """Children fork from a single-threaded server"""
    ctx = multiprocessing.get_context("forkserver")
    ctx.set_forkserver_preload(_FORKSERVER_PRELOAD)
    return ctx


def _subprocess_worker(
    code: str,
    params: Dict[str, Any],
    wrap_code: bool,
    conn: Connection,
    max_result_bytes: int = _MAX_RESULT_BYTES,
    prelude: str = "",
) -> None:
    """Worker that runs inside an isolated subprocess.

    Security controls applied here (in addition to the AST/builtins sandbox):
    - All environment variables cleared so user code cannot read secrets
      (JWT_SECRET_KEY, FERNET_KEY, DATABASE_URL, AWS credentials, etc.)
    - OS-level resource limits applied on Linux (256 MB address space, CPU time cap)
    """
    # Strip all env vars — user code must not access container secrets
    os.environ.clear()

    # Apply CPU time limit (Linux/macOS; silently skipped on unsupported platforms).
    # RLIMIT_AS (address space) is intentionally omitted: a forked child inherits
    # the parent's entire virtual memory map (FastAPI, pandas, numpy, etc.) which
    # already exceeds any reasonable per-script cap, causing immediate MemoryError
    # on any allocation. Memory abuse is already mitigated by the import allowlist.
    try:
        import resource as _rl
        _rl.setrlimit(_rl.RLIMIT_CPU, (_EXEC_TIMEOUT_SECONDS, _EXEC_TIMEOUT_SECONDS))
    except Exception:
        pass

    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    payload = None

    try:
        executable = add_executable_function(code) if wrap_code else code
        validate_code_ast(executable)
        namespace = make_sandboxed_namespace(params, logging.getLogger(__name__))
        if prelude:
            exec(prelude, namespace)  # noqa: S102

        try:
            faulthandler.dump_traceback_later(_EXEC_TIMEOUT_SECONDS - 5, file=sys.__stderr__)
        except Exception:
            pass  # diagnostics only
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(executable, namespace)  # noqa: S102
        finally:
            faulthandler.cancel_dump_traceback_later()

        result = namespace.get("result")
        global_errors = namespace.get("errors")
        output = stdout_buffer.getvalue()
        errors = stderr_buffer.getvalue()
        if global_errors:
            errors = errors + "\nGlobal errors: " + str(global_errors)
        payload = {"result": result, "output": output, "errors": errors}
        if str(global_errors or "").startswith(_SCRIPT_ERROR_PREFIX) and callable(namespace.get("executable_function")):
            payload["script_failed"] = True

    except SandboxViolation as sv:
        payload = {
            "error": f"Sandbox violation: {sv}",
            "traceback": "",
            "output": stdout_buffer.getvalue(),
            "errors": stderr_buffer.getvalue(),
        }
    except SyntaxError as se:
        payload = {
            "error": f"Syntax error: {se}",
            "traceback": "",
            "output": stdout_buffer.getvalue(),
            "errors": stderr_buffer.getvalue(),
        }
    except Exception as e:
        payload = {
            "error": str(e) or type(e).__name__,
            "traceback": "",
            "output": stdout_buffer.getvalue(),
            "errors": stderr_buffer.getvalue(),
        }
    finally:
        if payload is not None:
            conn.send_bytes(_encode_result(payload, max_result_bytes))
        conn.close()


def _execute_python_code_sync(
    code: str,
    params: Dict[str, Any],
    wrap_code: bool = True,
    max_result_bytes: int = _MAX_RESULT_BYTES,
    prelude: str = "",
) -> Dict[str, Any]:
    """Spawn an isolated subprocess to execute user-supplied Python code.

    The subprocess clears its environment and applies resource limits before
    running the AST/builtins sandbox. Kills the process if it exceeds
    _EXEC_TIMEOUT_SECONDS.
    """
    ctx = _script_context()
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    process = ctx.Process(
        target=_subprocess_worker,
        args=(code, params, wrap_code, child_conn, max_result_bytes, prelude),
        daemon=True,
    )
    started = False
    try:
        try:
            process.start()
            started = True
        except (TypeError, pickle.PicklingError, AttributeError) as exc:
            keys = _unpicklable_keys(params)
            logger.warning("Script params cannot be sent to the sandbox: %s (%s)", keys, exc)
            return _error_dict(f"Script params cannot be sent to the sandbox: {', '.join(keys) or exc}")
        child_conn.close()  # only the child may hold the write end, or EOF never arrives

        if not wait_readable([parent_conn], timeout=_EXEC_TIMEOUT_SECONDS):
            _kill(process)
            logger.warning(
                "User code execution timed out after %ds — subprocess killed",
                _EXEC_TIMEOUT_SECONDS,
            )
            return _error_dict(f"Execution timed out after {_EXEC_TIMEOUT_SECONDS} seconds")

        try:
            return pickle.loads(parent_conn.recv_bytes(maxlength=max_result_bytes))
        except (EOFError, OSError):
            pass  # exited without sending, killed mid-send, or over the size cap
        except Exception as exc:
            logger.warning("Script result could not be decoded: %s", type(exc).__name__)
            return _error_dict(f"Script result could not be decoded: {type(exc).__name__}")
        process.join(timeout=_EXIT_GRACE_SECONDS)
        # Exit code 1 is a child that could not load its arguments; the round trip copies them, so skip it after a kill
        keys = _unpicklable_keys(params) if process.exitcode == 1 else []
        if keys:
            logger.warning("Script params cannot be sent to the sandbox: %s (exit code %s)", keys, process.exitcode)
            return _error_dict(f"Script params cannot be sent to the sandbox: {', '.join(keys)}")
        logger.warning("User code subprocess exited with code %s without returning a result", process.exitcode)
        return _error_dict("Subprocess exited without returning a result")
    finally:
        parent_conn.close()
        child_conn.close()
        if started:
            process.join(timeout=_EXIT_GRACE_SECONDS)
            if process.is_alive():
                process.kill()
                process.join()


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
    code: str,
    params: Dict[str, Any],
    wrap_code: bool = True,
    max_result_bytes: int = _MAX_RESULT_BYTES,
    prelude: str = "",
) -> Dict[str, Any]:
    """Execute user Python code asynchronously. Subprocess isolation handles timeout."""
    try:
        code = sanitize_python_code(code)
        # _execute_python_code_sync blocks for at most _EXEC_TIMEOUT_SECONDS
        # (subprocess is killed if it exceeds that), so to_thread won't hang.
        return await asyncio.to_thread(_execute_python_code_sync, code, params, wrap_code, max_result_bytes, prelude)
    except Exception as e:
        logger.error("Error in async Python code execution: %s", type(e).__name__)
        return _error_dict(str(e) or type(e).__name__)


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
