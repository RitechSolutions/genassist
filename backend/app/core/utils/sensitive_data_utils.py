import re
from typing import Any

_SENSITIVE_FIELD_RE = re.compile(
    r"(?:"
    r"password|passphrase|secret|token|api[_-]?key|access[_-]?key|private[_-]?key"
    r"|refresh[_-]?token|auth|authorization|cookie|session"
    r"|ssn|sin|nin|tax|passport"
    r"|credit|card|cvv|cvc|iban|swift|routing|account[_-]?number"
    r")",
    re.IGNORECASE,
)

_SENSITIVE_KV_RE = re.compile(
    r"(?P<prefix>(?:^|[^\w-]))"
    r"(?P<key>"
    r"password|passphrase|secret|token|api[_-]?key|access[_-]?key|private[_-]?key"
    r"|refresh[_-]?token|auth|authorization|cookie|session"
    r")"
    r"(?P<ws1>\s*)"
    r"(?P<sep>[:=])"
    r"(?P<ws2>\s*)"
    r"(?P<val>[^\s,;)\]}]+)",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_JWT_RE = re.compile(
    r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"
)
_PHONE_RE = re.compile(
    r"\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,3}\)?[\s-]?)?\d{3}[\s-]?\d{4}\b"
)
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_HEX_TOKEN_RE = re.compile(r"\b[a-f0-9]{32,}\b", re.IGNORECASE)
_B64URL_TOKEN_RE = re.compile(r"\b[a-zA-Z0-9_-]{32,}\b")

TOKEN_REDACTION_LABEL = "[TOKEN]"


def is_sensitive_field_name(field_name: str) -> bool:
    return bool(_SENSITIVE_FIELD_RE.search(field_name or ""))


def looks_like_sensitive_string(value: str) -> bool:
    """
    Heuristic value-based detection to avoid persisting secrets/PII even when
    the column name is benign (e.g. "note", "description", "value").
    """
    if not value:
        return False

    if _JWT_RE.search(value):
        return True
    if _EMAIL_RE.search(value):
        return True
    if _SSN_RE.search(value):
        return True

    # Credit-card-ish numbers: basic check (length + mostly digits)
    if _CC_RE.search(value):
        digits = re.sub(r"\D", "", value)
        if 13 <= len(digits) <= 19:
            return True

    # Phone numbers (avoid very short false positives)
    if _PHONE_RE.search(value) and len(re.sub(r"\D", "", value)) >= 10:
        return True

    # Long tokens/keys: hex or base64url-ish (common API keys, hashes, etc.)
    if _HEX_TOKEN_RE.search(value):
        return True
    if _B64URL_TOKEN_RE.search(value):
        # Reduce false positives: require some mix (not all letters)
        has_digit = any(ch.isdigit() for ch in value)
        has_alpha = any(ch.isalpha() for ch in value)
        if has_digit and has_alpha:
            return True

    return False


def redact_sensitive_substrings(value: Any, *, redacted: str = "[REDACTED]") -> Any:
    """
    Redact only the sensitive *parts* of a string (email/JWT/SSN/etc.), leaving
    surrounding context intact. Non-strings are returned unchanged.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        return value

    def _redact_sensitive_kv(m: re.Match) -> str:
        return (
            f"{m.group('prefix')}{m.group('key')}{m.group('ws1')}"
            f"{m.group('sep')}{m.group('ws2')}{redacted}"
        )

    # First, redact obvious sensitive key/value pairs in free-form strings.
    redacted_value = _SENSITIVE_KV_RE.sub(_redact_sensitive_kv, value)

    # Redact sensitive-looking substrings with corresponding labels.
    for pattern, label in (
        (_JWT_RE,       TOKEN_REDACTION_LABEL),
        (_EMAIL_RE,     "[EMAIL]"),
        (_SSN_RE,       "[SSN]"),
        (_CC_RE,        "[CARD]"),
        (_PHONE_RE,     "[PHONE]"),
        (_HEX_TOKEN_RE, TOKEN_REDACTION_LABEL),
        (_B64URL_TOKEN_RE, TOKEN_REDACTION_LABEL),
    ):
        redacted_value = pattern.sub(label, redacted_value)

    return redacted_value


def redact_if_sensitive(field_name: str, value: Any, *, redacted: str = "[REDACTED]") -> Any:
    if value is None:
        return None
    if is_sensitive_field_name(field_name):
        return redacted
    if isinstance(value, str) and looks_like_sensitive_string(value) and field_name != "json_changes":
        return redacted
    return value


# Values shorter than this are not masked via substring replacement, to avoid
# corrupting unrelated content (e.g. a value of "1" or "on" appearing everywhere).
_MIN_HIDDEN_VALUE_LEN = 2


def build_hidden_value_map(
    hidden_keys: set,
    node_statuses: dict | None = None,
    fallback_values: dict | None = None,
) -> dict:
    """Build a ``{real_value_str: "[PARAM_NAME]"}`` map for hidden parameters.

    For each hidden key, the real value is resolved from the chatInputNode
    ``output`` inside ``nodeExecutionStatus`` (authoritative validated data),
    falling back to ``fallback_values`` (e.g. request metadata) when absent.

    Values that are None/empty, booleans, or whose string form is shorter than
    ``_MIN_HIDDEN_VALUE_LEN`` are skipped to avoid over-matching. This means a
    very short hidden value may not be masked — an accepted limitation.
    """
    if not hidden_keys:
        return {}

    resolved: dict = {}

    # Prefer the chatInputNode output (the validated_data the node produced).
    if isinstance(node_statuses, dict):
        for node_info in node_statuses.values():
            if not isinstance(node_info, dict):
                continue
            if node_info.get("type") == "chatInputNode":
                output = node_info.get("output", {})
                if isinstance(output, dict):
                    for key in hidden_keys:
                        if key in output:
                            resolved[key] = output[key]

    if fallback_values:
        for key in hidden_keys:
            if key not in resolved and key in fallback_values:
                resolved[key] = fallback_values[key]

    value_map: dict = {}
    for key, value in resolved.items():
        if value is None or isinstance(value, bool):
            continue
        value_str = str(value)
        if len(value_str) < _MIN_HIDDEN_VALUE_LEN:
            continue
        value_map[value_str] = f"[{str(key).upper()}]"

    return value_map


def mask_hidden_values(data: Any, value_map: dict) -> Any:
    """Recursively replace known hidden values with their ``[PARAM_NAME]`` placeholder.

    - String values: each real value is substring-replaced (longest first so
      overlapping values mask correctly).
    - Scalar int/float: replaced with the placeholder string when its string
      form matches a known value.
    - Booleans and other types are left unchanged.
    """
    if not value_map:
        return data

    # Longest values first so a value that contains another masks correctly.
    ordered = sorted(value_map.items(), key=lambda kv: len(kv[0]), reverse=True)

    def _mask(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: _mask(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            masked = [_mask(v) for v in value]
            return type(value)(masked) if isinstance(value, tuple) else masked
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            for real, placeholder in ordered:
                if real in value:
                    value = value.replace(real, placeholder)
            return value
        if isinstance(value, (int, float)):
            return value_map.get(str(value), value)
        return value

    return _mask(data)


def redact_structure(value: Any, *, redacted: str = "[REDACTED]") -> Any:
    """
    Recursively redact sensitive values in a nested structure (dict/list/scalars).

    - Dict keys are checked for sensitivity (e.g. "authorization", "token").
    - String values are scrubbed for embedded secrets (JWTs, key=value, etc.).
    """
    if value is None:
        return None

    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if is_sensitive_field_name(key_str):
                out[k] = redacted
                continue
            out[k] = redact_structure(v, redacted=redacted)
        return out

    if isinstance(value, (list, tuple)):
        redacted_items = [redact_structure(v, redacted=redacted) for v in value]
        return type(value)(redacted_items) if isinstance(value, tuple) else redacted_items

    if isinstance(value, str):
        return redact_sensitive_substrings(value, redacted=redacted)

    return value

