"""AST-based policy for validating customer SQL as read-only.

This module does not execute SQL. It classifies a query as read-only using
SQLGlot's AST for the dialects GenAssist actually supports.

Policy source: SQLGlot 26.33.0 spike. Do not treat this as a generic SQL linter.
"""

from __future__ import annotations

import logging

import sqlglot
from sqlglot import exp

from .validation_result import ValidationResult

READ_ONLY_SQL_FALLBACK_REASON = "Only read-only queries are permitted."
READ_ONLY_SQL_BLOCKED_PREFIX = "SQL execution blocked:"

logger = logging.getLogger(__name__)

SQLGLOT_DIALECTS = {
    "postgresql": "postgres",
    "timescaledb": "postgres",
    "timedb": "postgres",
    "mysql": "mysql",
    "sql": "mysql",
    "mssql": "tsql",
    "sqlite": "sqlite",
    "snowflake": "snowflake",
}

# Concrete Query subclasses observed in sqlglot 26.33.0. Listed explicitly so a
# future Query subtype is fail-closed rather than silently allowed.
_ALLOWED_ROOTS = (
    exp.Select,
    exp.Union,
    exp.Except,
    exp.Intersect,
    exp.Subquery,
)

# exp.Replace is a string function (Func), not DML. MySQL REPLACE INTO parses as
# Command and is rejected via that class. Do not add Replace here.
_FORBIDDEN_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.LoadData,
    exp.Grant,
    exp.Command,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Use,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Show,
    exp.Describe,
    exp.Analyze,
    exp.Refresh,
    exp.Kill,
    exp.Comment,
)

_SELECT_INTO_MESSAGE = "SELECT INTO is not allowed in read-only SQL."
_ROW_LOCK_MESSAGE = "Row-locking SELECT statements are not allowed."
_MYSQL_EXECUTABLE_COMMENT_MESSAGE = "MySQL executable comments are not allowed in read-only SQL."


def read_only_sql_blocked_message(validation: ValidationResult) -> str:
    """User-facing copy for a failed read-only policy check.

    Uses the policy-generated reason, never database/driver text.
    """
    reason = validation.error_message or READ_ONLY_SQL_FALLBACK_REASON
    return f"{READ_ONLY_SQL_BLOCKED_PREFIX} {reason}"


def validate_read_only_sql(query: str, db_type: str) -> ValidationResult:
    """Return whether ``query`` is exactly one read-only SQL statement.

    Fail closed: unknown dialect, parse failure, multiple statements, disallowed
    root, or any forbidden node anywhere in the AST all yield ``is_valid=False``.
    Does not raise for ordinary invalid SQL.
    """
    if not isinstance(query, str) or not query.strip():
        return ValidationResult(False, "SQL query is empty.")

    dialect = _resolve_dialect(db_type)
    if dialect is None:
        return ValidationResult(False, f"Unsupported database type for SQL validation: {db_type}")

    # SQLGlot 26.33.0 does not expose MySQL /*! ... */ bodies as executable AST
    # nodes (comment metadata, or no tokens when the whole query is one). Scan
    # the raw SQL for that opener before trusting the AST. Regular /* */ and --
    # comments are not matched.
    if dialect == "mysql" and _contains_mysql_executable_comment(query):
        return ValidationResult(False, _MYSQL_EXECUTABLE_COMMENT_MESSAGE)

    try:
        statements = sqlglot.parse(query, dialect=dialect)
    except Exception as exc:  # fail closed on any parser error
        logger.debug("Read-only SQL parse failed (%s): %s", type(exc).__name__, exc)
        return ValidationResult(False, "SQL query could not be safely parsed.")

    # A single trailing semicolon is one Select. An extra semicolon may append
    # None; count only real statements so `SELECT 1;` remains valid.
    parsed = [stmt for stmt in statements if stmt is not None]
    if not parsed:
        return ValidationResult(False, "SQL query could not be safely parsed.")
    if len(parsed) != 1:
        return ValidationResult(
            False,
            f"Expected a single SELECT statement, found {len(parsed)}. "
            "Multiple SQL statements are not allowed.",
        )

    root = parsed[0]
    if not _is_allowed_root(root):
        return ValidationResult(
            False,
            f"SQL statement type '{type(root).__name__}' is not allowed. Only read-only queries are permitted.",
            query_type=type(root).__name__,
        )

    identifier_placeholder = _find_identifier_placeholder(root)
    if identifier_placeholder is not None:
        return ValidationResult(
            False,
            "SQL parameters cannot be used as table names; "
            "use a fixed table name in the query.",
            query_type=type(root).__name__,
        )

    select_violation = _validate_select_properties(root, type(root).__name__)
    if select_violation is not None:
        return select_violation

    forbidden = _find_forbidden_node(root)
    if forbidden is not None:
        return ValidationResult(
            False,
            f"Unsafe SQL operation detected: {type(forbidden).__name__}.",
            query_type=type(root).__name__,
        )

    return ValidationResult(True, query_type=type(root).__name__)


def _resolve_dialect(db_type: str) -> str | None:
    if not isinstance(db_type, str):
        return None
    return SQLGLOT_DIALECTS.get(db_type.strip().lower())


def _contains_mysql_executable_comment(query: str) -> bool:
    """True if ``query`` contains a MySQL ``/*!`` opener outside quoted text.

    Distinguishes the executable-comment form from ``/*!`` inside ``'...'``,
    ``"..."``, or backtick identifiers. Does not classify SQL otherwise.
    """
    i = 0
    n = len(query)
    while i < n:
        ch = query[i]
        if ch == "'":
            i = _skip_mysql_quoted(query, i, "'")
            continue
        if ch == '"':
            i = _skip_mysql_quoted(query, i, '"')
            continue
        if ch == "`":
            i = _skip_mysql_quoted(query, i, "`")
            continue
        if ch == "#":
            i = _skip_to_line_end(query, i)
            continue
        if ch == "-" and i + 1 < n and query[i + 1] == "-":
            after = i + 2
            # MySQL treats ``--`` as a comment only when followed by whitespace.
            if after >= n or query[after].isspace():
                i = _skip_to_line_end(query, i)
                continue
        if ch == "/" and i + 1 < n and query[i + 1] == "*":
            if i + 2 < n and query[i + 2] == "!":
                return True
            i = _skip_c_style_comment(query, i)
            continue
        i += 1
    return False


def _skip_mysql_quoted(query: str, start: int, quote: str) -> int:
    """Return the index after a quoted span starting at ``start``.

    Handles doubled single quotes, double quotes, and backticks, plus backslash
    escapes. Unterminated quotes consume the rest of the string.
    """
    i = start + 1
    n = len(query)
    while i < n:
        ch = query[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == quote:
            if i + 1 < n and query[i + 1] == quote:
                i += 2
                continue
            return i + 1
        i += 1
    return n


def _skip_c_style_comment(query: str, start: int) -> int:
    """Skip a non-executable ``/* ... */`` comment starting at ``start``."""
    i = start + 2
    n = len(query)
    while i + 1 < n:
        if query[i] == "*" and query[i + 1] == "/":
            return i + 2
        i += 1
    return n


def _skip_to_line_end(query: str, start: int) -> int:
    """Return the index of the next CR or LF, or ``len(query)`` if none.

    Does not consume the terminator. ``\\r\\n`` therefore resumes on CR, and
    the caller treats CR/LF as ordinary characters so both Unix and Windows
    line endings end a ``#`` / ``--`` comment.
    """
    i = start
    n = len(query)
    while i < n and query[i] not in "\n\r":
        i += 1
    return i


def _is_allowed_root(expression: exp.Expression) -> bool:
    return isinstance(expression, _ALLOWED_ROOTS)


def _find_forbidden_node(expression: exp.Expression) -> exp.Expression | None:
    for node in expression.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            return node
    return None


def _find_identifier_placeholder(expression: exp.Expression) -> exp.Placeholder | None:
    """Return a bound placeholder used where SQL requires a table identifier."""
    for node in expression.find_all(exp.Placeholder):
        if isinstance(node.parent, exp.Table):
            return node
    return None


def _validate_select_properties(
    expression: exp.Expression, query_type: str
) -> ValidationResult | None:
    """Reject SELECT INTO and row-locking SELECT (FOR UPDATE / FOR SHARE)."""
    for node in expression.walk():
        if isinstance(node, exp.Into):
            return ValidationResult(False, _SELECT_INTO_MESSAGE, query_type=query_type)
        if isinstance(node, exp.Lock):
            return ValidationResult(False, _ROW_LOCK_MESSAGE, query_type=query_type)
        if isinstance(node, exp.Select):
            if node.args.get("into") is not None:
                return ValidationResult(False, _SELECT_INTO_MESSAGE, query_type=query_type)
            locks = node.args.get("locks")
            if locks:
                return ValidationResult(False, _ROW_LOCK_MESSAGE, query_type=query_type)
    return None
