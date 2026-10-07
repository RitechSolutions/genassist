"""Policies for exposing and logging exception details safely."""

import re
import traceback
from pathlib import Path

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

# Errors whose detail is deliberately written for an end user and contains no
# internal information. Their detail may be returned outside development too.
CLIENT_SAFE_DETAIL_KEYS = frozenset(
    {
        ErrorKey.SSO_MICROSOFT_OAUTH_ERROR,
        ErrorKey.SSO_MICROSOFT_USER_DENIED,
        ErrorKey.SSO_MICROSOFT_REDIRECT_NOT_ALLOWED,
        ErrorKey.SSO_MICROSOFT_NOT_CONFIGURED,
        ErrorKey.SSO_MICROSOFT_DISABLED,
        ErrorKey.EVALUATION_BUNDLE_INVALID,
        ErrorKey.DATASET_FILE_IMPORT_INVALID,
        ErrorKey.RULE_CONFIG_INVALID,
        ErrorKey.TOOL_USAGE_CONFIG_INVALID,
        ErrorKey.PROMPT_CONTEXT_INVALID,
        ErrorKey.PROMPT_FIELD_NOT_SUPPORTED,
        ErrorKey.PROMPT_VERSION_CONFLICT,
        ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID,
        ErrorKey.ML_EXTRACT_QUERY_FAILED,
        ErrorKey.ML_EXTRACT_FILE_UNAVAILABLE,
        ErrorKey.ML_EXTRACT_FILE_ENCODING_INVALID,
        ErrorKey.ML_EXTRACT_LIMIT_EXCEEDED,
        ErrorKey.ML_INFERENCE_INPUT_INVALID,
        ErrorKey.PROMPT_EVAL_TECHNIQUE_UNSUPPORTED,
        ErrorKey.PROMPT_CASE_SELECTION_INVALID,
        ErrorKey.PROMPT_OPTIMIZE_UNUSABLE,
        ErrorKey.READ_ONLY_SQL_BLOCKED,
    }
)

# Must match read_only_sql.read_only_sql_blocked_message(); importing that
# module here would pull sqlglot into every API error response.
READ_ONLY_SQL_BLOCKED_DETAIL_PREFIX = "SQL execution blocked:"


def sanitize_error_detail(text: str, max_len: int = 450) -> str:
    """Return a bounded single-line diagnostic with obvious secrets masked."""
    if not text:
        return ""
    sanitized = " ".join(str(text).split())
    sanitized = re.sub(
        r"(client_secret|client_assertion|password|refresh_token|code_verifier)"
        r"\s*[:=]\s*[^\s&\"']+",
        r"\1=***",
        sanitized,
        flags=re.I,
    )
    return sanitized[:max_len]


def exception_location(error: BaseException) -> str:
    """Return an exception type and code location without message or locals."""
    frames = traceback.extract_tb(error.__traceback__)
    if not frames:
        return type(error).__name__
    last = frames[-1]
    return (
        f"{type(error).__name__} at {Path(last.filename).name}:"
        f"{last.lineno} in {last.name}"
    )


def client_safe_error_detail(error: AppException) -> str | None:
    """Return an explicitly approved exception detail for an API client."""
    raw = (error.error_detail or "").strip()
    if not raw:
        return None
    sanitized = sanitize_error_detail(raw)
    if not sanitized or error.error_key not in CLIENT_SAFE_DETAIL_KEYS:
        return None
    if error.error_key == ErrorKey.READ_ONLY_SQL_BLOCKED:
        if not sanitized.startswith(READ_ONLY_SQL_BLOCKED_DETAIL_PREFIX):
            return None
    return sanitized
