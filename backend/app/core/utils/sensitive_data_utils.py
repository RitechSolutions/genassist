import re
from collections.abc import Mapping
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


def redact_bound_values(
    message: Any,
    parameters: Mapping[str, Any] | None,
    *,
    redacted: str = "[BOUND_VALUE]",
) -> str:
    """Remove bound parameter values from a database or driver message."""
    result = str(message)
    if not parameters:
        return result

    replacements: set[str] = set()
    has_short_value = False
    for value in parameters.values():
        if value is None:
            continue
        rendered = str(value)
        represented = repr(value)
        if len(rendered) == 1:
            has_short_value = True
        if represented:
            replacements.add(represented)
        if len(rendered) >= 2:
            replacements.add(rendered)

    if has_short_value:
        return "Database error details hidden for a query with bound parameters."

    for candidate in sorted(replacements, key=len, reverse=True):
        result = result.replace(candidate, redacted)
    return result


SQL_LITERAL_REDACTION = "***"
_SQL_COMMENT_REDACTION = f"/* {SQL_LITERAL_REDACTION} */"

_DOLLAR_QUOTE_OPEN_RE = re.compile(r"\$(?:[A-Za-z_]\w*)?\$")


def _sql_dialect(dialect: str | None) -> str:
    name = (dialect or "").strip().lower()
    return {"sql": "mysql", "postgres": "postgresql"}.get(name, name)


def _quoted_end(sql: str, start: int, close: str, backslash_escapes: bool) -> int:
    """Index just past the quote that closes the token opened at ``start``."""
    i = start + 1
    while i < len(sql):
        char = sql[i]
        if backslash_escapes and char == "\\":
            i += 2
        elif char == close:
            if sql[i + 1:i + 2] == close:  # doubled quote: '' or "" or ]]
                i += 2
            else:
                return i + 1
        else:
            i += 1
    return len(sql)  # unterminated: runs to the end


def _scan_sql(sql: str, dialect: str, backslash_escapes: bool) -> list[tuple[int, int, str]]:
    """Find string literals and comments as ``(start, end, kind)``.

    Quoted names ("o'brien", `o'brien`, [o'brien]) are skipped as a whole, so a
    quote inside a name or a comment never shifts where the strings start.
    """
    spans: list[tuple[int, int, str]] = []
    i, n = 0, len(sql)
    while i < n:
        char, pair = sql[i], sql[i:i + 2]
        line_comment = (
            (pair == "--" and (dialect != "mysql" or sql[i + 2:i + 3] in ("", " ", "\t", "\n", "\r")))
            or (char == "#" and dialect == "mysql")
            or (pair == "//" and dialect == "snowflake")
        )
        if line_comment:
            end = sql.find("\n", i)
            end = n if end < 0 else end
            spans.append((i, end, "comment"))
        elif pair == "/*":
            end = sql.find("*/", i + 2)
            end = n if end < 0 else end + 2
            spans.append((i, end, "comment"))
        elif char == "'" or (char == '"' and dialect == "mysql"):
            end = _quoted_end(sql, i, char, backslash_escapes)
            spans.append((i, end, "string"))
        elif char in '"`' or (char == "[" and dialect in ("mssql", "sqlite")):
            end = _quoted_end(sql, i, "]" if char == "[" else char, False)
        elif (
            char == "$"
            and dialect in ("", "postgresql", "snowflake")
            and not (i and (sql[i - 1].isalnum() or sql[i - 1] in "_$"))
            and (opening := _DOLLAR_QUOTE_OPEN_RE.match(sql, i))
        ):
            tag = opening.group(0)
            close = sql.find(tag, opening.end())
            end = n if close < 0 else close + len(tag)
            spans.append((i, end, "string"))
        else:
            end = i + 1
        i = max(end, i + 1)
    return spans


def _sql_redaction_spans(sql: str, dialect: str | None) -> list[tuple[int, int, str]]:
    """Strings and comments under both readings of a backslash.

    MySQL and Snowflake treat \\' as an escaped quote; PostgreSQL, SQL Server and
    SQLite end the string there ('C:\\'). Server settings can flip this, so a span
    is redacted when either reading says it is a string or a comment.
    """
    name = _sql_dialect(dialect)
    spans = set(_scan_sql(sql, name, True)) | set(_scan_sql(sql, name, False))
    return sorted(spans)


def _literal_contents(token: str) -> set[str]:
    """The value inside a literal token, both as written and unescaped."""
    if token.startswith("$"):
        tag = token[:token.index("$", 1) + 1]
        closed = len(token) >= 2 * len(tag) and token.endswith(tag)
        return {token[len(tag):len(token) - len(tag)] if closed else token[len(tag):]}
    quote = token[0]
    inner = token[1:-1] if len(token) > 1 and token.endswith(quote) else token[1:]
    return {inner, inner.replace(quote * 2, quote), inner.replace("\\" + quote, quote)}


def _masked_token(token: str, kind: str) -> str:
    if kind == "comment":
        return _SQL_COMMENT_REDACTION
    quote = '"' if token.startswith('"') else "'"
    return f"{quote}{SQL_LITERAL_REDACTION}{quote}"


def _apply_redaction_spans(text: str, spans: list[tuple[int, int, str]]) -> str:
    parts: list[str] = []
    position = 0
    for start, end, kind in spans:
        if end <= position:
            continue
        if start < position:
            # Overlaps the previous span (the two backslash readings disagree):
            # mask the rest of it too.
            if parts[-1] != SQL_LITERAL_REDACTION:
                parts.append(SQL_LITERAL_REDACTION)
        else:
            parts.append(text[position:start])
            parts.append(_masked_token(text[start:end], kind))
        position = end
    parts.append(text[position:])
    return "".join(parts)


def redact_sql_literals(sql: Any, *, dialect: str | None = None) -> str:
    """Mask every string literal and comment in SQL text, keeping keywords and names.

    ``WHERE password = 'secret'`` becomes ``WHERE password = '***'``.
    ``dialect`` is the datasource type (postgresql, mysql, mssql, sqlite,
    snowflake); it decides which quotes and comment markers apply.
    """
    text = str(sql)
    return _apply_redaction_spans(text, _sql_redaction_spans(text, dialect))


# How much of a driver message is searched for the query's values. The result
# is cut to a couple of thousand characters for the log anyway, and searching
# a long message for thousands of values would block the worker.
MAX_SCANNED_DB_MESSAGE = 8_000


def redact_sql_literal_values(
    message: Any,
    sql: Any,
    *,
    dialect: str | None = None,
) -> str:
    """Remove the string literals and comments of ``sql`` from a driver message about it.

    Drivers repeat the statement (SQLAlchemy's ``[SQL: ...]``) or a literal on
    its own (``invalid input syntax for type integer: "secret"``,
    ``Duplicate entry 'secret'``), so each literal's value is masked wherever
    it appears. A value is only masked as a whole word, so a literal such as
    'active' does not mangle a table named active_orders.

    Only the first ``MAX_SCANNED_DB_MESSAGE`` characters are kept, so the cost
    stays proportional to the query size even for thousands of values.
    """
    result = str(message)
    if not sql:
        return result

    sql = str(sql)
    spans = _sql_redaction_spans(sql, dialect)

    # The usual case: the whole statement is repeated. Masking that copy in one
    # pass leaves only the driver's own text to search.
    if sql in result:
        result = result.replace(sql, _apply_redaction_spans(sql, spans))

    tokens = {(sql[start:end], kind) for start, end, kind in spans}
    longest_token = max((len(token) for token, _kind in tokens), default=0)
    truncated = len(result) > MAX_SCANNED_DB_MESSAGE
    if truncated:
        result = result[:MAX_SCANNED_DB_MESSAGE]

    for token, kind in sorted(tokens, key=lambda item: len(item[0]), reverse=True):
        if token in result:
            result = result.replace(token, _masked_token(token, kind))

    values = {
        value
        for token, kind in tokens
        if kind == "string"
        for value in _literal_contents(token)
    }
    for value in sorted(values, key=len, reverse=True):
        # One-character values would match everywhere; their quoted form is
        # already masked above.
        if len(value.strip()) < 2 or value not in result:
            continue
        result = re.sub(
            rf"(?<!\w){re.escape(value)}(?!\w)",
            SQL_LITERAL_REDACTION,
            result,
        )

    if truncated:
        # A value cut in half at the end was not recognized; drop the tail it
        # could be in.
        result = result[:max(0, len(result) - longest_token)] + " [truncated]"
    return result


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
