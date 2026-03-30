"""Helpers for safe HTTP redirects (e.g. storage presigned URLs)."""

from typing import Optional
from urllib.parse import ParseResult, urlparse, urlunparse

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException

_AWS_S3_HOST_SUFFIXES = (".amazonaws.com", ".amazonaws.com.cn")


def _canonical_netloc(parsed: ParseResult) -> str:
    """Rebuild netloc from hostname and port only (no userinfo)."""
    host = parsed.hostname or ""
    if not host:
        return ""
    if ":" in host and not host.startswith("["):
        host_part = f"[{host}]"
    else:
        host_part = host
    if parsed.port:
        return f"{host_part}:{parsed.port}"
    return host_part


def _rebuild_http_url(parsed: ParseResult) -> str:
    scheme = parsed.scheme.lower()
    netloc = _canonical_netloc(parsed)
    return urlunparse(
        (
            scheme,
            netloc,
            parsed.path or "",
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def validate_s3_download_redirect_url(url: str, s3_endpoint_url: Optional[str]) -> str:
    """
    Ensure a redirect target is a plausible S3 (or S3-compatible) URL to reduce
    open-redirect risk if a URL were ever attacker-influenced.

    Returns a new URL string built from parsed components (not the original
    input reference) so static analysis can treat it as sanitized.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() not in ("http", "https"):
        raise AppException(
            ErrorKey.INTERNAL_ERROR,
            500,
            "Invalid download redirect: URL must use http or https",
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise AppException(
            ErrorKey.INTERNAL_ERROR,
            500,
            "Invalid download redirect: missing host",
        )

    if s3_endpoint_url:
        ep = urlparse(s3_endpoint_url.strip())
        ep_host = (ep.hostname or "").lower()
        if ep_host and host == ep_host:
            return _rebuild_http_url(parsed)

    if any(host.endswith(suffix) for suffix in _AWS_S3_HOST_SUFFIXES):
        return _rebuild_http_url(parsed)

    raise AppException(
        ErrorKey.INTERNAL_ERROR,
        500,
        "Invalid download redirect: host not allowed for storage",
    )
