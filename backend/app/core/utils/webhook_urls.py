"""Public URLs of webhook endpoints: ``{api}/webhook/execute/{id}?x-tenant-id=<slug>``."""

from typing import Annotated, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import Request
from pydantic import AfterValidator

from app.core.config.settings import settings
from app.core.tenant_scope import get_tenant_context


def build_public_url(base_url: Optional[str], request: Optional[Request], webhook_id: UUID) -> str:
    """A configured PUBLIC_API_URL wins over the caller's base_url and the request's own address."""
    base = settings.PUBLIC_API_URL or (base_url or "").strip().rstrip("/")
    if base:
        url = f"{base}/webhook/execute/{webhook_id}"
    elif request is not None:
        # GET and POST share this path
        address = request.url_for("webhook_handler_post", webhook_id=str(webhook_id))
        # TLS ends at the load balancer, so the request itself arrives over http
        proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
        if proto == "https":
            address = address.replace(scheme="https", port=None if address.port == 80 else address.port)
        url = str(address)
    else:
        raise ValueError("A webhook URL needs PUBLIC_API_URL, a base_url or the request")
    tenant_param = {settings.TENANT_HEADER_NAME.lower(): get_tenant_context()}
    return f"{url}?{urlencode(tenant_param)}"


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
