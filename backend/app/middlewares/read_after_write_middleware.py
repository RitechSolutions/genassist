"""
Read-your-writes guard for the read replica.

After a client completes a write, its reads are served by the writer for a short
window, so replica lag can never show it its own change late. Other clients keep
reading from the replica. Inactive unless a replica is configured.
"""

import base64
import hashlib
import json
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.utils import API_KEY_HEADER_NAME
from app.core.config.settings import settings
from app.core.tenant_scope import get_tenant_context
from app.db.read_routing import pin_reads_to_writer, unpin_reads

logger = logging.getLogger(__name__)

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_KEY_PREFIX = "read-pin"
# Starlette lower-cases header names; the test doubles use plain dicts.
_API_KEY_HEADER = API_KEY_HEADER_NAME.lower()
# Real payloads are a few hundred bytes. Anything larger is rejected before it is
# decoded, so an oversized header cannot cost parsing work or reach json.loads.
_MAX_PAYLOAD_SEGMENT = 4096


def _redis():
    from app.dependencies.dependency_injection import RedisString
    from app.dependencies.injector import injector

    return injector.get(RedisString)


def _has_bearer_scheme(authorization: str | None) -> bool:
    """Matches what OAuth2PasswordBearer accepts, so this agrees with ``auth`` on which
    credential the request is presenting."""
    return bool(authorization) and authorization.lower().startswith("bearer ")


def _bearer_subject(authorization: str | None) -> str | None:
    """User id from the bearer token payload. Not verified here: auth does that later,
    and this value only groups one user's requests for routing. Anything unparseable
    yields None, because this runs before authentication and must never raise."""
    if not _has_bearer_scheme(authorization):
        return None
    segments = authorization.split(" ", 1)[1].split(".")
    if len(segments) < 2 or len(segments[1]) > _MAX_PAYLOAD_SEGMENT:
        return None
    try:
        padded = segments[1] + "=" * (-len(segments[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict):
        return None
    subject = payload.get("user_id") or payload.get("sub")
    return str(subject) if subject else None


def _client_identity(request: Request) -> str | None:
    """Who the request belongs to for routing, resolved in the order ``auth`` uses: a
    bearer token wins outright, and the API key is read only when there is none. The two
    are namespaced apart so a user id can never collide with a key value."""
    authorization = request.headers.get("authorization")
    if _has_bearer_scheme(authorization):
        subject = _bearer_subject(authorization)
        return f"user\x00{subject}" if subject is not None else None
    api_key = request.headers.get(_API_KEY_HEADER)
    return f"key\x00{api_key}" if api_key else None


def _client_key(request: Request) -> str | None:
    """Both the tenant and the identity are caller-supplied, so the key is a digest: it
    stays a fixed length, the API key value never leaves the process, and two different
    callers cannot produce the same key.
    """
    identity = _client_identity(request)
    if identity is None:
        return None
    scope = f"{get_tenant_context()}\x00{identity}".encode()
    return f"{_KEY_PREFIX}:{hashlib.sha256(scope).hexdigest()[:32]}"


class ReadAfterWriteMiddleware(BaseHTTPMiddleware):
    """Pin a client's reads to the writer for a few seconds after one of its writes."""

    async def dispatch(self, request: Request, call_next):
        if not self._enabled():
            return await call_next(request)

        client_key = _client_key(request)
        if client_key is None:
            return await call_next(request)

        if request.method in READ_METHODS:
            return await self._serve_read(request, call_next, client_key)

        response = await call_next(request)
        if response.status_code < 400:
            await self._remember_write(client_key)
        return response

    @staticmethod
    def _enabled() -> bool:
        return settings.read_replica_enabled and settings.DB_READ_PIN_AFTER_WRITE_SECONDS > 0

    async def _serve_read(self, request: Request, call_next, client_key: str):
        if not await self._wrote_recently(client_key):
            return await call_next(request)
        token = pin_reads_to_writer()
        try:
            return await call_next(request)
        finally:
            unpin_reads(token)

    @staticmethod
    async def _wrote_recently(client_key: str) -> bool:
        try:
            return bool(await _redis().exists(client_key))
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Read pin lookup failed, serving this read from the writer: %s", exc)
            return True

    @staticmethod
    async def _remember_write(client_key: str) -> None:
        try:
            await _redis().set(client_key, "1", ex=settings.DB_READ_PIN_AFTER_WRITE_SECONDS)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Read pin could not be stored: %s", exc)
