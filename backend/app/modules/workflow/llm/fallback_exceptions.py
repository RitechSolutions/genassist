"""
Provider-agnostic exception classification for LLM fallback chains.

When a model call fails we must decide whether the failure is *transient*
(worth retrying / falling back to the next provider) or *permanent* (fail fast —
retrying a bad API key or a malformed request just wastes the whole chain).

Two layers are combined:
  1. A broad tuple of base SDK exception classes to *catch* (`retryable_catch_tuple`).
     Imports are guarded so a missing optional SDK never breaks module import.
  2. `is_retryable(exc)` — the actual fall-back vs. fail-fast decision, using both
     isinstance checks for known timeout/connection errors and a generic HTTP
     status-code probe (`429`/`5xx` retry, `4xx` fail fast).
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# Metadata key stamped onto the responding message so token usage can be attributed
# to the provider that actually served the request (which may be a fallback).
# Defined here (a lightweight module) so usage utilities can import it without
# pulling in langchain via fallback_chat_model.
FALLBACK_PROVIDER_ID_KEY = "__fallback_provider_id__"

# HTTP status codes that represent a transient/recoverable condition.
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
# HTTP status codes that represent a permanent/client error — never retry these.
FAIL_FAST_STATUS_CODES = frozenset({400, 401, 403, 404, 405, 406, 422})

# AWS Bedrock / botocore error codes (exc.response["Error"]["Code"]) that are
# transient. botocore doesn't expose a `.status_code`, so we match on these too.
RETRYABLE_AWS_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "Throttling",
        "TooManyRequestsException",
        "ProvisionedThroughputExceededException",
        "ServiceUnavailableException",
        "ServiceUnavailable",
        "InternalServerException",
        "InternalFailure",
        "ModelTimeoutException",
        "ModelNotReadyException",
        "RequestTimeout",
        "RequestTimeoutException",
    }
)


def _collect_base_exceptions() -> tuple[type[BaseException], ...]:
    """Build the broad tuple of exception classes worth catching.

    Always includes builtin timeout/connection errors. Provider SDK base classes
    are added only if the SDK is importable, so optional dependencies never break
    this module.
    """
    bases: list[type[BaseException]] = [TimeoutError, ConnectionError, asyncio.TimeoutError]

    try:
        import openai

        bases.append(openai.OpenAIError)
    except Exception:  # pragma: no cover - SDK optional
        logger.debug("openai SDK not importable; skipping its exceptions in fallback classification")

    try:
        import anthropic

        bases.append(anthropic.AnthropicError)
    except Exception:  # pragma: no cover - SDK optional
        logger.debug("anthropic SDK not importable; skipping its exceptions in fallback classification")

    try:
        import httpx

        bases.append(httpx.HTTPError)
    except Exception:  # pragma: no cover - SDK optional
        logger.debug("httpx not importable; skipping its exceptions in fallback classification")

    try:
        import botocore.exceptions as boto_exc  # AWS Bedrock

        bases.append(boto_exc.BotoCoreError)  # connection/read timeouts, etc.
        bases.append(boto_exc.ClientError)  # throttling / service errors
    except Exception:  # pragma: no cover - SDK optional
        logger.debug("botocore not importable; skipping its exceptions in fallback classification")

    try:
        import google.api_core.exceptions as g_exc  # Gemini / Vertex via LangChain

        bases.append(g_exc.GoogleAPIError)
    except Exception:  # pragma: no cover - SDK optional
        logger.debug("google.api_core not importable; skipping its exceptions in fallback classification")

    # De-duplicate while preserving order.
    seen: set[type[BaseException]] = set()
    unique: list[type[BaseException]] = []
    for b in bases:
        if b not in seen:
            seen.add(b)
            unique.append(b)
    return tuple(unique)


# Computed once at import time. Used both as the `except (...)` target inside
# FallbackChatModel and as `retry_if_exception_type=...` for per-model retries.
_RETRYABLE_CATCH_TUPLE = _collect_base_exceptions()


def retryable_catch_tuple() -> tuple[type[BaseException], ...]:
    """Broad tuple of base exception classes to catch around a model call.

    Catching is intentionally broad; the fine-grained retry-vs-fail-fast decision
    is made by `is_retryable`. Pass this to `Runnable.with_retry(retry_if_exception_type=...)`.
    """
    return _RETRYABLE_CATCH_TUPLE


def _extract_status_code(exc: BaseException) -> int | None:
    """Best-effort extraction of an HTTP status code from a provider exception."""
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    if response is not None:
        # openai/anthropic/httpx expose an object with .status_code ...
        status = getattr(response, "status_code", None)
        if isinstance(status, int):
            return status
        # ... botocore (Bedrock) exposes a dict: response["ResponseMetadata"]["HTTPStatusCode"].
        if isinstance(response, dict):
            status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            if isinstance(status, int):
                return status
    # Google (google.api_core / google.genai) exposes the HTTP status as `.code`
    # (an HTTPStatus IntEnum, which is an int). Accept it only in the HTTP range so
    # we don't misread an unrelated int `.code` on some other exception type.
    code = getattr(exc, "code", None)
    if isinstance(code, int) and 100 <= int(code) <= 599:
        return int(code)
    return None


def _aws_error_code(exc: BaseException) -> str | None:
    """Extract the AWS/botocore error code (e.g. 'ThrottlingException'), if any."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = (response.get("Error") or {}).get("Code")
        if isinstance(code, str):
            return code
    return None


def is_retryable(exc: BaseException) -> bool:
    """Decide whether `exc` should trigger a retry / fallback to the next provider.

    Fall back on: timeouts, connection errors, rate limits, and 5xx/transient HTTP
    statuses. Fail fast on: authentication, permission, and bad-request (4xx) errors.
    Unknown exceptions default to NOT retryable (fail fast) so genuine bugs surface
    instead of silently burning through the whole chain.
    """
    # Connection-level failures never carry a status code but are always transient.
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return True

    try:
        import httpx

        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout)):
            return True
    except Exception:  # pragma: no cover - SDK optional
        pass

    # Provider SDKs expose connection/timeout subclasses with no status code.
    for mod_name, attrs in (
        ("openai", ("APITimeoutError", "APIConnectionError")),
        ("anthropic", ("APITimeoutError", "APIConnectionError")),
    ):
        try:
            mod = __import__(mod_name)
            classes = tuple(getattr(mod, a) for a in attrs if hasattr(mod, a))
            if classes and isinstance(exc, classes):
                return True
        except Exception:  # pragma: no cover - SDK optional
            continue

    # AWS Bedrock (botocore): connection/read timeouts have no status code, and
    # throttle/service errors carry the status in a dict + an error Code string.
    try:
        import botocore.exceptions as boto_exc

        if isinstance(
            exc,
            (
                boto_exc.ReadTimeoutError,
                boto_exc.ConnectTimeoutError,
                boto_exc.ConnectionError,
                boto_exc.EndpointConnectionError,
            ),
        ):
            return True
    except Exception:  # pragma: no cover - SDK optional
        pass

    aws_code = _aws_error_code(exc)
    if aws_code is not None:
        if aws_code in RETRYABLE_AWS_ERROR_CODES:
            return True
        # fall through to the status-code check below (e.g. AccessDenied -> 403 -> fail fast)

    # Google (Gemini / Vertex via google.api_core): transient types. Most also carry
    # an HTTP `.code` handled below, but a few (e.g. RetryError) do not.
    try:
        import google.api_core.exceptions as g_exc

        transient_google = tuple(
            getattr(g_exc, n)
            for n in (
                "ServiceUnavailable",
                "DeadlineExceeded",
                "ResourceExhausted",
                "TooManyRequests",
                "InternalServerError",
                "Aborted",
                "RetryError",
            )
            if hasattr(g_exc, n)
        )
        if transient_google and isinstance(exc, transient_google):
            return True
    except Exception:  # pragma: no cover - SDK optional
        pass

    # Status-code based classification for everything else.
    status = _extract_status_code(exc)
    if status is not None:
        if status in FAIL_FAST_STATUS_CODES:
            return False
        if status in RETRYABLE_STATUS_CODES:
            return True
        # Any other 5xx is transient; any other 4xx is a client error.
        return 500 <= status < 600

    # No status code and not a known transient type → fail fast.
    return False