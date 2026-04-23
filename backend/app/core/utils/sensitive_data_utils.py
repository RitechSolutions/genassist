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

    # Then redact sensitive-looking substrings (more specific first).
    for pattern in (
        _JWT_RE,
        _EMAIL_RE,
        _SSN_RE,
        _CC_RE,
        _PHONE_RE,
        _HEX_TOKEN_RE,
        _B64URL_TOKEN_RE,
    ):
        redacted_value = pattern.sub(redacted, redacted_value)

    return redacted_value


def redact_if_sensitive(field_name: str, value: Any, *, redacted: str = "[REDACTED]") -> Any:
    if value is None:
        return None
    if is_sensitive_field_name(field_name):
        return redacted
    if isinstance(value, str) and looks_like_sensitive_string(value) and field_name != "json_changes":
        return redacted
    return value

