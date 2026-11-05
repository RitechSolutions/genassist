"""Public URLs of webhook endpoints: ``{api}/webhook/execute/{id}?x-tenant-id=<slug>``."""

from typing import Annotated, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import Request
from pydantic import AfterValidator
from starlette.datastructures import URL

from app.core.config.settings import settings
from app.core.tenant_scope import get_tenant_context


def build_public_url(base_url: Optional[str], request: Optional[Request], webhook_id: UUID) -> str:
    """A configured PUBLIC_API_URL wins over the caller's base_url and the request's own address."""
    caller_base = (base_url or "").strip().rstrip("/")
    if settings.PUBLIC_API_URL:
        url = f"{settings.PUBLIC_API_URL}/webhook/execute/{webhook_id}"
    elif caller_base:
        url = _with_forwarded_scheme(f"{caller_base}/webhook/execute/{webhook_id}", request)
    elif request is not None:
        # GET and POST share this path
        address = request.url_for("webhook_handler_post", webhook_id=str(webhook_id))
        url = _with_forwarded_scheme(str(address), request)
    else:
        raise ValueError("A webhook URL needs PUBLIC_API_URL, a base_url or the request")
    tenant_param = {settings.TENANT_HEADER_NAME.lower(): get_tenant_context()}
    return f"{url}?{urlencode(tenant_param)}"


def _with_forwarded_scheme(url: str, request: Optional[Request]) -> str:
    """Give an http URL on the request's own host the scheme the client used.

    TLS ends at the load balancer, so the request itself arrives over http.
    """
    if request is None:
        return url
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    address = URL(url)
    # A caller's base_url can be any string
    try:
        on_request_host = address.scheme == "http" and address.netloc.lower() == request.url.netloc.lower()
        port = None if address.port == 80 else address.port
    except ValueError:
        return url
    return str(address.replace(scheme="https", port=port)) if proto == "https" and on_request_host else url


def with_public_address(url: str) -> str:
    """Move a stored http URL on PUBLIC_API_URL's host to the setting's https address.

    Rows keep the address they were created with, which can predate the setting.
    """
    if not settings.PUBLIC_API_URL:
        return url
    public = urlsplit(settings.PUBLIC_API_URL)
    # Rows can hold any string a caller sent as base_url
    try:
        stored = urlsplit(url)
    except ValueError:
        return url
    upgrade = public.scheme == "https" and stored.scheme == "http" and stored.hostname == public.hostname
    return urlunsplit(stored._replace(scheme="https", netloc=public.netloc)) if upgrade else url


PublicUrl = Annotated[str, AfterValidator(with_public_address)]
