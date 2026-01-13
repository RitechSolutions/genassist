"""
Utils for the engine
"""

import logging
import json
import re
from typing import Any, Optional

from app.modules.workflow.engine.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


def flatten_dict(data: dict, prefix: str = "", separator: str = ".") -> dict:
    """Flatten a nested dictionary using dot notation

    Args:
        data: Dictionary to flatten
        prefix: Prefix for the keys
        separator: Separator to use between keys (default: ".")

    Returns:
        Flattened dictionary with dot notation keys
    """
    flattened = {}

    for key, value in data.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key

        if isinstance(value, dict) and value:
            # Recursively flatten nested dictionaries
            flattened.update(flatten_dict(value, new_key, separator))
        else:
            # Add the value directly
            flattened[new_key] = value

    return flattened


def find_all_vars(obj_str: str) -> list:
    """
    Find all variables in a string
    """
    return re.findall(r"{{.*?}}", obj_str)


def get_nested_value(obj: Any, path: str) -> Any:
    """
    Safely retrieve a nested value from an object using dot notation.

    Args:
        obj: The object to traverse (dict, object, or any value)
        path: Dot-separated path like "data.user.name"

    Returns:
        The value at the specified path, or None if not found
    """
    if not path:
        return obj

    keys = path.split(".")
    current = obj

    for key in keys:
        if current is None:
            return None

        if isinstance(current, dict):
            current = current.get(key)
        elif hasattr(current, key):
            try:
                current = getattr(current, key)
            except AttributeError:
                return None
        else:
            return None

    return current


def _resolve_variable_from_state(var_name: str, state: WorkflowState) -> Optional[Any]:
    """
    Resolve a variable value from the workflow state.

    Args:
        var_name: The variable name to resolve
        state: The workflow state object

    Returns:
        The resolved value, or None if not found
    """
    state_value = state.get_value(var_name)
    return state_value if state_value is not None else None


def _resolve_variable_from_source(var_name: str, source_output: Any) -> Any:
    """
    Resolve a variable value from the source node output.

    Handles both {{source}} and {{source.property}} patterns.

    Args:
        var_name: The variable name (e.g., "source" or "source.property")
        source_output: The source node's output

    Returns:
        The resolved value, or empty string if not available
    """
    if var_name == "source":
        return source_output
    else:
        property_path = var_name[7:]  # Remove "source." prefix

        return get_nested_value(source_output, property_path)


def _resolve_variable_from_direct_input(var_name: str, direct_input: dict) -> Any:
    """
    Resolve a variable value from direct input.

    Handles both {{direct_input}} and {{direct_input.property}} patterns.

    Args:
        var_name: The variable name (e.g., "direct_input" or "direct_input.property")
        direct_input: The direct input dictionary

    Returns:
        The resolved value, or empty string if not found
    """
    if var_name == "direct_input":
        # Return the entire direct_input
        return direct_input
    else:
        # Extract the property path after "direct_input."
        property_path = var_name[13:]  # Remove "direct_input." prefix
        nested_value = get_nested_value(direct_input, property_path)
        return nested_value


def _resolve_variable_value(
    var_name: str, state: WorkflowState, source_output: Any, direct_input: dict
) -> tuple[Optional[Any], bool]:
    """
    Resolve a variable value from available sources (state, source, or direct_input).

    Args:
        var_name: The variable name to resolve
        state: The workflow state object
        source_output: The source node's output
        direct_input: The direct input dictionary

    Returns:
        Tuple of (resolved_value, was_resolved)
    """

    # Try source pattern
    if var_name.startswith("source"):
        resolved_value = _resolve_variable_from_source(var_name, source_output)
        if resolved_value is None:
            # try state
            resolved_value = state.get_value(var_name)
        return resolved_value, True

    # Try direct_input pattern
    if var_name.startswith("direct_input"):
        resolved_value = _resolve_variable_from_direct_input(var_name, direct_input)
        if resolved_value is None:
            # try state
            resolved_value = state.get_value(var_name)
        return resolved_value, True

    return state.get_value(var_name), True


def _is_in_string_context(json_string: str, var_start: int) -> bool:
    """
    Determine if a variable position is within a string context in JSON.

    Args:
        json_string: The JSON string to analyze
        var_start: The starting position of the variable

    Returns:
        True if the variable is inside a string, False otherwise
    """
    if var_start == -1:
        return False

    # Count unescaped quotes before the variable
    # If odd number, we're inside a string
    quote_count_before = 0
    for i in range(var_start):
        if json_string[i] == '"':
            # Check if it's escaped
            num_backslashes = 0
            j = i - 1
            while j >= 0 and json_string[j] == "\\":
                num_backslashes += 1
                j -= 1
            if num_backslashes % 2 == 0:  # Not escaped
                quote_count_before += 1

    # Odd number of quotes means we're inside a string
    return quote_count_before % 2 == 1


def _convert_json_escapes_for_code_context(json_string: str) -> str:
    """
    Convert JSON escape sequences for Python code context while preserving JSON validity.

    The issue: When JSON with escape sequences like \n is embedded in Python code as a string,
    the escape sequences need to be properly handled. Converting to actual characters breaks JSON,
    so we replace problematic escape sequences with spaces to avoid "invalid escape" errors.

    Args:
        json_string: The JSON string with escaped sequences (after quote escaping)

    Returns:
        String with escape sequences converted for safe use in Python code
    """
    # Replace escape sequences that might cause "invalid escape" errors in Python
    # with spaces (as per user's original solution). This preserves JSON validity
    # while preventing Python from interpreting escape sequences incorrectly.
    escape_replacements = {
        "\\n": " ",  # newline -> space
        "\\t": " ",  # tab -> space
        "\\r": " ",  # carriage return -> space
        "\\b": " ",  # backspace -> space
        "\\f": " ",  # form feed -> space
    }

    result = json_string
    # Replace escape sequences, being careful not to replace parts of \\\\ (escaped backslash)
    # Process from right to left or use regex with negative lookbehind
    for escape_seq, replacement in escape_replacements.items():
        # Pattern: match escape_seq but not when it's part of \\\\X (escaped backslash + X)
        # Negative lookbehind: (?<!\\) means "not preceded by a single backslash"
        pattern = r"(?<!\\)" + re.escape(escape_seq)
        result = re.sub(pattern, replacement, result)

    # Handle escaped backslashes: \\\\ -> \\ (single backslash in Python code)
    # This must be done after other replacements to avoid interfering
    result = result.replace("\\\\", "\\")

    return result


def _is_in_code_field_context(json_string: str, var_start: int) -> bool:
    """
    Determine if a variable position is within a "code" field context.

    This checks if the variable is inside a JSON string value for a "code" key,
    which typically contains Python code that will be executed.

    Args:
        json_string: The JSON string to analyze
        var_start: The starting position of the variable

    Returns:
        True if the variable is inside a "code" field value, False otherwise
    """
    if var_start == -1:
        return False

    # Find the opening quote of the string value containing this variable
    # by looking backwards for an unescaped quote
    value_start = -1
    for i in range(var_start - 1, -1, -1):
        if json_string[i] == '"':
            # Check if it's escaped
            num_backslashes = 0
            j = i - 1
            while j >= 0 and json_string[j] == "\\":
                num_backslashes += 1
                j -= 1
            if num_backslashes % 2 == 0:  # Not escaped
                value_start = i
                break

    if value_start == -1:
        return False

    # Look backwards from value_start to find the key
    # Search for pattern: "code"\s*:\s*"
    # Find the colon before the value_start
    colon_pos = -1
    for i in range(value_start - 1, -1, -1):
        if json_string[i] == ":":
            # Check if it's in a string (shouldn't be, but be safe)
            # For simplicity, assume colon before value quote is the separator
            colon_pos = i
            break
        elif json_string[i] in " \t\n\r":
            continue
        elif json_string[i] == '"':
            # Hit another quote, might be the key
            break

    if colon_pos == -1:
        return False

    # Look backwards from colon to find "code"
    code_pattern = '"code"'
    pattern_end = colon_pos
    # Skip whitespace before colon
    for i in range(colon_pos - 1, -1, -1):
        if json_string[i] not in " \t\n\r":
            pattern_end = i + 1
            break

    # Check if "code" appears just before the colon
    if pattern_end >= len(code_pattern):
        potential_match = json_string[pattern_end - len(code_pattern):pattern_end]
        if potential_match == code_pattern:
            return True

    return False


def _encode_replacement_value(
    replacement_value: Any, var_name: str, json_string: str, var_pattern: str
) -> str:
    """
    Encode a replacement value appropriately based on its type and context.

    Args:
        replacement_value: The value to encode
        var_name: The variable name (for logging)
        json_string: The JSON string containing the variable
        var_pattern: The variable pattern (e.g., "{{var_name}}")

    Returns:
        The encoded replacement string
    """
    try:
        # Always encode the replacement value as JSON first
        json_encoded = json.dumps(replacement_value)

        # Check if the variable is in a string context
        var_start = json_string.find(var_pattern)
        in_string_context = _is_in_string_context(json_string, var_start)
        in_code_context = _is_in_code_field_context(json_string, var_start)

        if isinstance(replacement_value, str):
            # For strings, always remove quotes since template provides them
            # The JSON encoding already properly escapes all special characters
            json_replacement = json_encoded[1:-1]
            logger.debug(
                f"Replaced {var_name} with escaped string content: {json_replacement}"
            )
        else:
            # For objects, behavior depends on context
            if in_string_context:
                # In string context, escape quotes so object can be embedded in string
                json_replacement = json_encoded.replace('"', '\\"')

                # Special handling for code context: if JSON with escape sequences is being inserted
                # into Python code, we need to handle escape sequences to avoid "invalid escape" errors
                # We replace escape sequences like \\n with spaces to prevent issues while preserving
                # JSON validity (converting to actual characters would break JSON structure)
                if in_code_context:
                    json_replacement = _convert_json_escapes_for_code_context(
                        json_replacement
                    )

                logger.debug(
                    f"Replaced {var_name} with escaped JSON object for string context: {json_replacement}"
                )
            else:
                # In object context, use the JSON as-is
                json_replacement = json_encoded
                logger.debug(
                    f"Replaced {var_name} with JSON object for object context: {json_replacement}"
                )

        return json_replacement

    except (TypeError, ValueError) as e:
        # Fallback to string representation
        logger.warning(
            f"Failed to JSON encode replacement value for {var_name}: {e}. Using string representation."
        )
        string_replacement = json.dumps(str(replacement_value))[1:-1]  # Remove quotes
        logger.debug(
            f"Used fallback string encoding for {var_name}: {string_replacement}"
        )
        return string_replacement


def replace_config_vars(
    config: dict,
    state: WorkflowState,
    source_output: Any,
    direct_input: Optional[dict] = None,
) -> tuple[dict, dict]:
    """
    Replace both @value and {{value}} patterns in a string with values from a dictionary.

    Special handling for source.property patterns:
    - {{source.property}} will retrieve the property from the source node's output
    - If source node output is a dict and contains the property, that value is used
    - If source node output is not available or doesn't contain the property, empty string is used

    Args:
        config: The configuration dictionary containing variables
        state: The workflow state object
        source_output: The source node's output
        direct_input: Optional direct input dictionary

    Returns:
        tuple: (resolved_config, replacements_made)
            - resolved_config: The configuration dictionary with all variables replaced
            - replacements_made: Dictionary of variable_name -> replacement_value for all replacements
    """
    if not config:
        return config, {}

    if direct_input is None:
        direct_input = {}

    string_config = json.dumps(config)
    replacements_made = {}

    # Find all variables in the config
    variables = find_all_vars(string_config)

    # Resolve and replace each variable
    for var_pattern in variables:
        var_name = var_pattern.replace("{{", "").replace("}}", "")

        # Resolve the variable value from available sources
        replacement_value, was_resolved = _resolve_variable_value(
            var_name, state, source_output, direct_input
        )

        if was_resolved:
            replacements_made[var_name] = replacement_value

            # Encode and replace the variable in the JSON string
            json_replacement = _encode_replacement_value(
                replacement_value, var_name, string_config, var_pattern
            )
            string_config = string_config.replace(var_pattern, json_replacement)

    # Parse the result back to a dictionary
    try:
        object_result = json.loads(string_config)
        return object_result, replacements_made
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error after variable replacement: {e}")
        logger.error(f"Problematic JSON string: {string_config}")
        logger.error(f"Applied replacements: {replacements_made}")
        # Return original config as fallback
        return config, replacements_made
    except Exception as e:
        logger.error(f"Unexpected error loading JSON: {e}")
        return config, replacements_made
