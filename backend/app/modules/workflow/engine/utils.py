"""
Utils for the engine
"""

import json
import logging
import re
from typing import Any, Optional

from app.core.utils.sensitive_data_utils import redact_sensitive_substrings
from app.core.utils.string_utils import truncate_for_log
from app.modules.workflow.engine.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

# JSON fields whose values are treated as executable code (Python, etc.)
CODE_FIELD_NAMES = ["code", "pythonScript", "pythonCode"]

PARAM_STYLE_NAMED = "named"
PARAM_STYLE_PYFORMAT = "pyformat"
_SUPPORTED_PARAM_STYLES = {PARAM_STYLE_NAMED, PARAM_STYLE_PYFORMAT}
_VARIABLE_RE = re.compile(r"{{([^\s{}]+)}}")


class QueryVariableError(ValueError):
    """A workflow variable appears in an unsupported SQL context."""


class BoundParameters(dict[str, Any]):
    """Parameter values plus their user-facing workflow variable names."""

    def __init__(self):
        super().__init__()
        self.variable_names: dict[str, str] = {}


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
    Find all variables in a string (excludes variables with spaces)
    """
    return re.findall(r"{{[^\s{}]+}}", obj_str)


def has_volatile_template_vars(template: Any) -> bool:
    """Whether a raw template contains any substitutable {{var}}"""
    if not isinstance(template, str) or not template:
        return False
    return bool(find_all_vars(template))


def _unique_vars(template: str) -> list[str]:
    """Return unique workflow variable tokens while preserving their order."""
    return list(dict.fromkeys(find_all_vars(template)))


def bind_config_vars(
    template: str,
    state: WorkflowState,
    source_output: Any,
    direct_input: Optional[dict] = None,
    param_style: str = PARAM_STYLE_NAMED,
    db_type: str = "",
) -> tuple[str, BoundParameters]:
    """Replace workflow variables with driver bind parameters.

    Returns a statement and parameter dictionary that can be passed separately
    to a database driver. A variable wrapped in a single pair of SQL quotes is
    replaced together with those quotes so the resulting token remains a bind
    parameter rather than becoming a string literal.
    """
    parameters = BoundParameters()
    if not template:
        return template, parameters
    if param_style not in _SUPPORTED_PARAM_STYLES:
        raise ValueError(f"Unsupported SQL parameter style: {param_style}")

    direct_input = direct_input or {}
    normalized_db_type = str(db_type).strip().lower()
    mysql_mapping = normalized_db_type in {"mysql", "sql"}
    parts: list[tuple[str, bool]] = []
    bind_names: dict[str, str] = {}

    def add_literal(value: str) -> None:
        parts.append((value, False))

    def add_variable(var_name: str, following_index: int) -> None:
        bind_name = bind_names.get(var_name)
        if bind_name is None:
            bind_suffix = re.sub(r"[^0-9a-zA-Z_]", "_", var_name)
            bind_name = f"wf_{len(bind_names)}_{bind_suffix}"
            bind_names[var_name] = bind_name
            value, _ = _resolve_variable_value(
                var_name,
                state,
                source_output,
                direct_input,
            )
            if value is None:
                logger.warning(
                    "Workflow variable %s did not resolve; bound as NULL",
                    var_name,
                )
            parameters[bind_name] = value
            parameters.variable_names[bind_name] = var_name

        placeholder = f":{bind_name}" if param_style == PARAM_STYLE_NAMED else f"%({bind_name})s"
        if template[following_index : following_index + 2] == "::":
            placeholder = f"({placeholder})"
        parts.append((placeholder, True))

    i = 0
    while i < len(template):
        if template.startswith("--", i) and (
            not mysql_mapping
            or i + 2 >= len(template)
            or template[i + 2].isspace()
        ):
            end = _sql_line_end(template, i + 2)
            add_literal(template[i:end])
            i = end
            continue
        if mysql_mapping and template[i] == "#":
            end = _sql_line_end(template, i + 1)
            add_literal(template[i:end])
            i = end
            continue
        if template.startswith("/*", i):
            closing = template.find("*/", i + 2)
            end = len(template) if closing == -1 else closing + 2
            add_literal(template[i:end])
            i = end
            continue

        dollar_tag = _postgres_dollar_quote_at(template, i)
        if dollar_tag:
            closing = template.find(dollar_tag, i + len(dollar_tag))
            end = len(template) if closing == -1 else closing + len(dollar_tag)
            span = template[i:end]
            if _VARIABLE_RE.search(span):
                raise QueryVariableError(_embedded_variable_message(normalized_db_type))
            add_literal(span)
            i = end
            continue

        ch = template[i]
        if ch in {"'", '"', "`"}:
            end, closed = _sql_quoted_end(
                template,
                i,
                ch,
                backslash_escapes=mysql_mapping,
            )
            span = template[i:end]
            content = span[1:-1] if closed else span[1:]
            matches = list(_VARIABLE_RE.finditer(content))
            if not matches:
                add_literal(span)
            else:
                exact = _VARIABLE_RE.fullmatch(content)
                if ch == "'" and exact:
                    add_variable(exact.group(1), end)
                elif ch == '"' and exact and normalized_db_type in {"mysql", "sql"}:
                    add_variable(exact.group(1), end)
                elif ch in {'"', "`"}:
                    raise QueryVariableError(
                        "Workflow variables can only supply values, not table or "
                        "column names. Put the name directly in the query."
                    )
                else:
                    raise QueryVariableError(_embedded_variable_message(normalized_db_type))
            i = end
            continue

        if ch == "[" and normalized_db_type == "mssql":
            end = _sql_bracket_identifier_end(template, i)
            span = template[i:end]
            if _VARIABLE_RE.search(span):
                raise QueryVariableError(
                    "Workflow variables can only supply values, not table or "
                    "column names. Put the name directly in the query."
                )
            add_literal(span)
            i = end
            continue

        match = _VARIABLE_RE.match(template, i)
        if match:
            add_variable(match.group(1), match.end())
            i = match.end()
            continue

        add_literal(ch)
        i += 1

    if param_style == PARAM_STYLE_PYFORMAT and parameters:
        statement = "".join(value if is_bind else value.replace("%", "%%") for value, is_bind in parts)
    else:
        statement = "".join(value for value, _ in parts)
    return statement, parameters


def _sql_line_end(template: str, start: int) -> int:
    newline_positions = [
        position for position in (template.find("\n", start), template.find("\r", start)) if position != -1
    ]
    return min(newline_positions) if newline_positions else len(template)


def _sql_quoted_end(
    template: str,
    start: int,
    quote: str,
    *,
    backslash_escapes: bool,
) -> tuple[int, bool]:
    i = start + 1
    while i < len(template):
        if backslash_escapes and template[i] == "\\" and i + 1 < len(template):
            i += 2
            continue
        if template[i] == quote:
            if i + 1 < len(template) and template[i + 1] == quote:
                i += 2
                continue
            return i + 1, True
        i += 1
    return len(template), False


def _sql_bracket_identifier_end(template: str, start: int) -> int:
    i = start + 1
    while i < len(template):
        if template[i] == "]":
            if i + 1 < len(template) and template[i + 1] == "]":
                i += 2
                continue
            return i + 1
        i += 1
    return len(template)


def _postgres_dollar_quote_at(template: str, start: int) -> str | None:
    if template[start] != "$":
        return None
    match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", template[start:])
    return match.group(0) if match else None


def _embedded_variable_message(db_type: str) -> str:
    if db_type in {"mysql", "sql", "mssql"}:
        example = "LIKE CONCAT('%', {{search}}, '%')"
    else:
        example = "LIKE '%' || {{search}} || '%'"
    return (
        "Workflow variables must be complete SQL values, not part of a quoted "
        f"literal. Use database concatenation instead, for example: {example}."
    )


def find_code_param_vars(code_string: str) -> list:
    """
    Find all variable names referenced via params.get("varName") or param.get("varName")
    in a Python code string.

    Matches patterns like:
        params.get("variableName", None)
        params.get('variableName', None)
        param.get("variableName", None)

    Args:
        code_string: The Python code string to scan

    Returns:
        List of unique variable names found in params.get() calls
    """
    if not code_string:
        return []
    matches = re.findall(r'params?\.get\(\s*["\']([^"\']+)["\']', code_string)
    return list(dict.fromkeys(matches))


def extract_code_params(
    data: dict,
    state: WorkflowState,
    source_output: Any,
    direct_input: Optional[dict] = None,
) -> dict:
    """
    Scan code fields in the config for params.get("varName") patterns,
    resolve each variable from state/source/direct_input, and return
    a dictionary of resolved params to be injected at Python execution time.

    This handles cases where Python scripts access variables via
    params.get("variableName", None) instead of {{variableName}} templates.

    Args:
        config: The node configuration dictionary (already resolved by replace_config_vars)
        state: The workflow state object
        source_output: The source node's output
        direct_input: Optional direct input dictionary

    Returns:
        Dictionary of {variable_name: resolved_value} for all params.get() references
    """
    if not data:
        return {}

    if direct_input is None:
        direct_input = {}

    code_params = {}

    # Scan known code fields for params.get() patterns
    for field in CODE_FIELD_NAMES:
        code_string = data.get(field, "")
        if not code_string:
            continue

        var_names = find_code_param_vars(code_string)
        for var_name in var_names:
            if var_name in code_params:
                continue
            resolved_value, _ = _resolve_variable_value(var_name, state, source_output, direct_input)
            # Only include params that actually resolved to a value.
            # When the value is None, we omit it so the Python code's
            # own default in params.get("varName", default) takes effect.
            if resolved_value is not None:
                code_params[var_name] = resolved_value
                logger.debug("Resolved code param '%s' = %s", var_name, truncate_for_log(str(resolved_value)))
            else:
                logger.debug(
                    "Skipping code param '%s' (resolved to None, letting code default apply)",
                    var_name,
                )

    return code_params


_PATH_TOKEN_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _parse_path_tokens(path: str) -> list[str | int]:
    """Parse dot/bracket paths like ``prediction[0].result`` into traversal tokens."""
    tokens: list[str | int] = []
    for match in _PATH_TOKEN_RE.finditer(path):
        if match.group(1) is not None:
            tokens.append(match.group(1))
        elif match.group(2) is not None:
            tokens.append(int(match.group(2)))
    return tokens


def _access_path_segment(current: Any, key: str | int) -> Any:
    """Traverse one segment of a nested path."""
    if current is None:
        return None

    if isinstance(current, list):
        if isinstance(key, int):
            index = key
        elif isinstance(key, str) and key.isdigit():
            index = int(key)
        else:
            return None
        if 0 <= index < len(current):
            return current[index]
        return None

    if isinstance(current, dict):
        if key in current:
            return current[key]
        if isinstance(key, str) and key.isdigit() and int(key) in current:
            return current[int(key)]
        if isinstance(key, int) and str(key) in current:
            return current[str(key)]
        return None

    if isinstance(key, str) and hasattr(current, key):
        try:
            return getattr(current, key)
        except AttributeError:
            return None

    return None


def get_nested_value(obj: Any, path: str) -> Any:
    """
    Safely retrieve a nested value from an object using dot/bracket notation.

    Args:
        obj: The object to traverse (dict, object, or any value)
        path: Path like "data.user.name" or "prediction[0].result"

    Returns:
        The value at the specified path, or None if not found
    """
    if not path:
        return obj

    current = obj
    for key in _parse_path_tokens(path):
        current = _access_path_segment(current, key)
        if current is None:
            return None

    return current


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

    # Look backwards from colon to find any of the known code field names
    pattern_end = colon_pos
    # Skip whitespace before colon
    for i in range(colon_pos - 1, -1, -1):
        if json_string[i] not in " \t\n\r":
            pattern_end = i + 1
            break

    # Check if any known code field name appears just before the colon
    for field_name in CODE_FIELD_NAMES:
        code_pattern = f'"{field_name}"'
        if pattern_end >= len(code_pattern):
            potential_match = json_string[pattern_end - len(code_pattern) : pattern_end]
            if potential_match == code_pattern:
                return True

    return False


def _encode_replacement_value(replacement_value: Any, var_name: str, json_string: str, var_pattern: str) -> str:
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
        # Check if the variable is in a string context
        var_start = json_string.find(var_pattern)
        in_string_context = _is_in_string_context(json_string, var_start)
        in_code_context = _is_in_code_field_context(json_string, var_start)

        # Always encode the replacement value as JSON first
        json_encoded = json.dumps(replacement_value)

        if isinstance(replacement_value, str):
            if in_string_context:
                # For strings inside JSON string fields, remove outer quotes
                # The JSON encoding already properly escapes all special characters.
                json_replacement = json_encoded[1:-1]
                logger.debug("Replaced %s with escaped string content: %s", var_name, truncate_for_log(redact_sensitive_substrings(json_replacement)))
            else:
                # In non-string context (e.g. whole JSON value), use JSON as-is
                json_replacement = json_encoded
                logger.debug("Replaced %s with JSON string value for object context: %s", var_name, truncate_for_log(redact_sensitive_substrings(json_replacement)))
        else:
            # Non-string values (objects, lists, numbers, bools, None)
            if in_string_context:
                if in_code_context:
                    # Original behavior for code fields:
                    # escape quotes so JSON can be embedded safely in Python code strings,
                    # then fix problematic escape sequences (like \n) for Python.
                    json_replacement = json_encoded.replace('"', '\\"')
                    json_replacement = _convert_json_escapes_for_code_context(json_replacement)
                    logger.debug(
                        f"Replaced {var_name} with escaped JSON object for code string context: {truncate_for_log(json_replacement)}"
                    )
                else:
                    # Plain JSON string field (e.g. templates):
                    # 1) Convert the value to JSON text
                    # 2) Treat that JSON text as a string value and JSON-encode it again,
                    #    then strip outer quotes so it fits into the existing JSON string.
                    # This avoids manual quote replacement which was double-escaping
                    # sequences like \"beard\" -> \\\\\"beard\\\\\".
                    json_text = json.dumps(replacement_value)
                    json_replacement = json.dumps(json_text)[1:-1]
                    logger.debug(f"Replaced {var_name} with JSON text for string context: {truncate_for_log(json_replacement)}")
            else:
                # In object context, use the JSON as-is
                json_replacement = json_encoded
                logger.debug(f"Replaced {var_name} with JSON object for object context: {truncate_for_log(json_replacement)}")

        return json_replacement

    except (TypeError, ValueError) as e:
        # Fallback to string representation
        logger.warning(f"Failed to JSON encode replacement value for {var_name}: {e}. Using string representation.")
        string_replacement = json.dumps(str(replacement_value))[1:-1]  # Remove quotes
        logger.debug(f"Used fallback string encoding for {var_name}: {truncate_for_log(string_replacement)}")
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
    if not variables:
        return config, {}

    unique_vars = _unique_vars(string_config)

    # Phase 1: resolve all variables and compute their encoded replacements.
    # Context detection uses the *original* string so earlier replacements
    # cannot corrupt the quote structure used by _is_in_string_context.
    encoded_replacements: dict[str, str] = {}
    for var_pattern in unique_vars:
        var_name = var_pattern[2:-2]

        replacement_value, was_resolved = _resolve_variable_value(
            var_name, state, source_output, direct_input
        )

        if was_resolved:
            replacements_made[var_name] = replacement_value
            encoded_replacements[var_pattern] = _encode_replacement_value(
                replacement_value, var_name, string_config, var_pattern
            )

    if not encoded_replacements:
        return config, replacements_made

    # Phase 2: single-pass replacement via re.sub.
    # The old loop did N sequential str.replace() calls on a string that
    # grew with each replacement (O(N * accumulated_size) — quadratic for
    # large payloads).  A single re.sub pass is O(original + total_output).
    var_regex = re.compile("|".join(re.escape(vp) for vp in encoded_replacements))
    result_string = var_regex.sub(
        lambda m: encoded_replacements[m.group(0)], string_config
    )

    # Phase 3: parse the result back to a dictionary
    try:
        object_result = json.loads(result_string)
        return object_result, replacements_made
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error after variable replacement: {e}")
        logger.error(f"Problematic JSON string: {truncate_for_log(result_string)}")
        logger.error(f"Applied replacements: {truncate_for_log(str(replacements_made))}")
        return config, replacements_made
    except Exception as e:
        logger.error(f"Unexpected error loading JSON: {e}")
        return config, replacements_made
