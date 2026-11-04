"""Unit tests for ZendeskConnector OAuth client-credentials support.

Zendesk is removing API tokens on 2027-04-30, so the connector supports two auth
methods: the legacy API token (HTTP Basic ``email/token``) and the OAuth2
client-credentials grant (Bearer access token from ``/oauth/tokens``). These tests
cover auth-method resolution, credential validation, and that requests send the
right auth (Basic vs Bearer), refreshing the token once on a 401.

httpx is faked at the module level because ``_get_access_token`` opens its own
client (unlike ``_make_request``), so patching ``_make_request`` alone would not
intercept the token exchange.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.modules.integration.zendesk import ZendeskConnector, _zendesk_error_details

_OAUTH = {
    "subdomain": "acme",
    "auth_method": "oauth_client_credentials",
    "client_id": "client-id",
    "client_secret": "client-secret",
}


def _resp(status: int, url: str, *, json=None, text=""):
    """Build a real httpx.Response so raise_for_status()/json() behave normally."""
    req = httpx.Request("GET", url)
    if json is not None:
        return httpx.Response(status, json=json, request=req)
    return httpx.Response(status, text=text, request=req)


def _patch_httpx(responses):
    """Patch httpx.AsyncClient with a fake that serves ``responses`` in order.

    Returns a ``calls`` list of (method, url, headers) tuples so tests can assert
    the auth header sent on each request. All requests (API calls and the OAuth
    token exchange) go through httpx.AsyncClient.request.
    """
    calls = []
    queue = list(responses)

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, json=None, params=None, headers=None):
            calls.append((method, url, headers))
            return queue.pop(0)

    patcher = patch(
        "app.modules.integration.zendesk.httpx.AsyncClient", _FakeClient
    )
    return patcher, calls


# --------------------------------------------------------------------------- #
# Auth-method resolution (synchronous, no network)
# --------------------------------------------------------------------------- #

def test_explicit_auth_method_wins():
    c = ZendeskConnector(subdomain="acme", auth_method="api_token", client_id="x", client_secret="y")
    assert c.auth_method == "api_token"


def test_explicit_client_credentials_imply_oauth():
    # No auth_method passed, but per-call client credentials are present.
    c = ZendeskConnector(subdomain="acme", client_id="x", client_secret="y", auth_method=None)
    assert c.auth_method == "oauth_client_credentials"


def test_defaults_to_api_token_without_credentials():
    c = ZendeskConnector(subdomain="acme", email="a@b.com", api_token="tok", auth_method=None)
    assert c.auth_method == "api_token"


def test_subdomain_and_token_url_normalized():
    c = ZendeskConnector(**_OAUTH)
    assert c.subdomain == "acme.zendesk.com"
    assert c.token_url == "https://acme.zendesk.com/oauth/tokens"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("acme", "acme.zendesk.com"),
        ("acme.zendesk.com", "acme.zendesk.com"),
        ("ACME", "acme.zendesk.com"),                    # lower-cased
        ("https://acme.zendesk.com/agent", "acme.zendesk.com"),  # scheme + path stripped
        ("acme:8080", "acme.zendesk.com"),               # port stripped
        ("acme.zendesk.com@evil.com", "acme.zendesk.com"),  # userinfo trick neutralized
        ("evil.com#", ""),                               # fragment trick -> host evil.com, rejected
        ("evil.com", ""),                                # different host rejected
        ("acme.zendesk.com.evil.com", ""),               # suffix spoof rejected
        ("<enter-value-here>", ""),                      # unconfigured placeholder rejected
        ("", ""),
    ],
)
def test_subdomain_normalization_blocks_ssrf(raw, expected):
    # The subdomain flows into the request URL; only a clean <label>.zendesk.com host
    # is allowed, so attacker-crafted values cannot redirect requests to another host.
    assert ZendeskConnector._normalize_subdomain(raw) == expected


# --------------------------------------------------------------------------- #
# Credential validation
# --------------------------------------------------------------------------- #

def test_require_credentials_oauth_missing_secret():
    with patch("app.modules.integration.zendesk.settings.ZENDESK_CLIENT_SECRET", None):
        c = ZendeskConnector(
            subdomain="acme", auth_method="oauth_client_credentials", client_id="id"
        )
    with pytest.raises(ValueError):
        c._require_credentials()


def test_require_credentials_api_token_missing_token():
    # The settings fallback for the token is a placeholder string, so neutralize it
    # to exercise the "no token" branch.
    with patch("app.modules.integration.zendesk.settings.ZENDESK_API_TOKEN", ""):
        c = ZendeskConnector(
            subdomain="acme", auth_method="api_token", email="a@b.com", api_token=None
        )
    with pytest.raises(ValueError):
        c._require_credentials()


# --------------------------------------------------------------------------- #
# Request auth: Bearer (OAuth) vs Basic (API token)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_oauth_request_sends_bearer_token():
    c = ZendeskConnector(**_OAUTH)
    responses = [
        _resp(200, c.token_url, json={"access_token": "TOKEN1"}),
        _resp(200, f"{c.base_url}/tickets/count.json", json={"count": {"value": 3}}),
    ]
    patcher, calls = _patch_httpx(responses)
    with patcher:
        result = await c._make_request("GET", f"{c.base_url}/tickets/count.json")

    assert result == {"count": {"value": 3}}
    # First call is the token exchange (POST to the token endpoint), then the API
    # call carrying the Bearer header.
    assert calls[0][0] == "POST" and calls[0][1] == c.token_url
    assert calls[1][2]["Authorization"] == "Bearer TOKEN1"


@pytest.mark.asyncio
async def test_oauth_refreshes_token_once_on_401():
    c = ZendeskConnector(**_OAUTH)
    url = f"{c.base_url}/tickets/count.json"
    responses = [
        _resp(200, c.token_url, json={"access_token": "TOKEN1"}),
        _resp(401, url, text="unauthorized"),  # stale token → 401
        _resp(200, c.token_url, json={"access_token": "TOKEN2"}),  # refreshed
        _resp(200, url, json={"count": {"value": 7}}),
    ]
    patcher, calls = _patch_httpx(responses)
    with patcher:
        result = await c._make_request("GET", url)

    assert result == {"count": {"value": 7}}
    # Two token exchanges (initial + forced refresh) and the retry carries the new token.
    token_exchanges = [x for x in calls if x[1] == c.token_url]
    assert len(token_exchanges) == 2
    assert calls[-1][2]["Authorization"] == "Bearer TOKEN2"


@pytest.mark.asyncio
async def test_api_token_mode_uses_basic_auth_no_token_exchange():
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )
    url = f"{c.base_url}/tickets/count.json"
    patcher, calls = _patch_httpx([_resp(200, url, json={"ok": True})])
    with patcher:
        result = await c._make_request("GET", url)

    assert result == {"ok": True}
    # No token endpoint call in API-token mode, and no Bearer header.
    assert all(x[1] != c.token_url for x in calls)
    assert calls[0][2] is None  # headers not set for Basic auth


# --------------------------------------------------------------------------- #
# test_connection wiring
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_test_connection_forwards_oauth_fields():
    """test_connection passes OAuth fields through and reports success."""
    with patch.object(
        ZendeskConnector, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"count": {"value": 0}}
        result = await ZendeskConnector.test_connection(
            {
                "subdomain": "acme",
                "auth_method": "oauth_client_credentials",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "oauth_scope": "read write",
            }
        )

    assert result == {"success": True, "message": "Successfully connected to Zendesk."}
    method, url = mock_request.await_args.args[:2]
    assert method == "GET"
    assert url.endswith("/tickets/count.json")


@pytest.mark.asyncio
async def test_test_connection_raises_on_auth_failure():
    with patch.object(
        ZendeskConnector, "_make_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = HTTPException(status_code=401, detail="invalid")
        with pytest.raises(HTTPException):
            await ZendeskConnector.test_connection(
                {
                    "subdomain": "acme",
                    "auth_method": "oauth_client_credentials",
                    "client_id": "client-id",
                    "client_secret": "client-secret",
                }
            )


# --------------------------------------------------------------------------- #
# Rejected requests: failure reason goes to the trace, never the response body
# --------------------------------------------------------------------------- #

_REJECTED = {
    "error": "RecordInvalid",
    "description": "Record validation errors",
    "details": {
        "requester": [
            {"description": "Requester: Email: john@example.com is invalid"}
        ]
    },
}


def _tracer_with_span():
    """A fake tracer whose ``trace()`` yields a ticket span, plus an open request span.

    The request span stands for the caller's own span (e.g. ``POST /chat``); it
    must never be marked failed by a ticket failure.
    """
    span = MagicMock()
    span.error = 0
    request_span = MagicMock()
    request_span.error = 0
    fake_tracer = MagicMock()
    fake_tracer.trace.return_value.__enter__.return_value = span
    fake_tracer.current_span.return_value = request_span
    return fake_tracer, span, request_span


@pytest.mark.asyncio
async def test_rejected_ticket_tags_span_and_does_not_log_body(caplog):
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )
    url = f"{c.base_url}/tickets.json"
    fake_tracer, span, request_span = _tracer_with_span()
    patcher, _ = _patch_httpx([_resp(422, url, json=_REJECTED)])

    with patcher, patch("app.modules.integration.zendesk.tracer", fake_tracer):
        result = await c.create_ticket(
            subject="s", description="d", requester_email="john@example.com"
        )

    assert result is None
    fake_tracer.trace.assert_called_once_with(
        "zendesk.create_ticket", resource="create_ticket"
    )
    assert span.error == 1
    # The caller's request span (which may still answer 200) stays clean.
    assert request_span.error == 0
    request_span.set_tag.assert_not_called()
    span.set_tag.assert_any_call("zendesk.status_code", 422)
    span.set_tag.assert_any_call("zendesk.error", "RecordInvalid")
    span.set_tag.assert_any_call("zendesk.field", "requester")
    assert "error=RecordInvalid field=requester" in caplog.text
    assert "john@example.com" not in caplog.text


@pytest.mark.asyncio
async def test_rejected_request_without_tracer_or_json_body(caplog):
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )
    url = f"{c.base_url}/tickets.json"
    patcher, _ = _patch_httpx([_resp(500, url, text="<html>oops</html>")])

    with patcher, patch("app.modules.integration.zendesk.tracer", None):
        with pytest.raises(HTTPException):
            await c._make_request("POST", url)

    assert "error=unknown field=unknown" in caplog.text
    assert "oops" not in caplog.text


@pytest.mark.parametrize(
    "body, expected",
    [
        (_REJECTED, ("RecordInvalid", "requester")),
        # OAuth-style errors nest the type under "title".
        ({"error": {"title": "Forbidden", "message": "x"}}, ("Forbidden", "unknown")),
        ({"error": "RecordNotFound"}, ("RecordNotFound", "unknown")),
        ({"details": {"email": [{"description": "a@b.com"}]}}, ("unknown", "email")),
        (["not", "a", "dict"], ("unknown", "unknown")),
        ({}, ("unknown", "unknown")),
    ],
)
def test_zendesk_error_details(body, expected):
    resp = _resp(422, "https://acme.zendesk.com/api/v2/tickets.json", json=body)
    assert _zendesk_error_details(resp) == expected


def test_zendesk_error_details_never_returns_descriptions():
    resp = _resp(422, "https://acme.zendesk.com/api/v2/tickets.json", json=_REJECTED)
    assert "john@example.com" not in "".join(_zendesk_error_details(resp))


@pytest.mark.asyncio
async def test_rejected_ticket_without_ddtrace(caplog):
    """Without ddtrace there is no span to tag; create_ticket still returns None."""
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )
    url = f"{c.base_url}/tickets.json"
    patcher, _ = _patch_httpx([_resp(422, url, json=_REJECTED)])

    with patcher, patch("app.modules.integration.zendesk.tracer", None):
        assert await c.create_ticket(subject="s", description="d") is None

    assert "error=RecordInvalid field=requester" in caplog.text


@pytest.mark.asyncio
async def test_oauth_rejected_ticket_tags_span():
    """The OAuth path goes through the same error handling as API-token auth."""
    c = ZendeskConnector(**_OAUTH)
    url = f"{c.base_url}/tickets.json"
    fake_tracer, span, _ = _tracer_with_span()
    patcher, _ = _patch_httpx(
        [
            _resp(200, c.token_url, json={"access_token": "TOKEN"}),
            _resp(422, url, json=_REJECTED),
        ]
    )

    with patcher, patch("app.modules.integration.zendesk.tracer", fake_tracer):
        result = await c.create_ticket(subject="s", description="d")

    assert result is None
    assert span.error == 1
    span.set_tag.assert_any_call("zendesk.field", "requester")


@pytest.mark.asyncio
async def test_raised_error_detail_has_no_response_body():
    """str(e) is logged by callers and recorded by ddtrace, so it must not hold the email."""
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )
    url = f"{c.base_url}/tickets/1.json"
    patcher, _ = _patch_httpx([_resp(422, url, json=_REJECTED)])

    with patcher:
        with pytest.raises(HTTPException) as exc:
            await c._make_request("GET", url)

    assert exc.value.status_code == 422
    assert "john@example.com" not in str(exc.value)
    assert "error=RecordInvalid field=requester" in exc.value.detail


@pytest.mark.asyncio
async def test_only_create_ticket_marks_span_failed():
    """Other calls handle their own errors; they must not fail the parent span."""
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )
    url = f"{c.base_url}/tickets/1.json"
    fake_tracer, span, request_span = _tracer_with_span()
    patcher, _ = _patch_httpx([_resp(404, url, json={"error": "RecordNotFound"})])

    with patcher, patch("app.modules.integration.zendesk.tracer", fake_tracer):
        assert await c.update_ticket(1, comment="x") is False

    fake_tracer.trace.assert_not_called()
    assert request_span.error == 0
    request_span.set_tag.assert_not_called()


@pytest.mark.asyncio
async def test_oauth_refresh_then_success_does_not_mark_span_failed():
    """An expired token (401) that is refreshed and retried is not a failed ticket."""
    c = ZendeskConnector(**_OAUTH)
    url = f"{c.base_url}/tickets.json"
    fake_tracer, span, _ = _tracer_with_span()
    patcher, _ = _patch_httpx(
        [
            _resp(200, c.token_url, json={"access_token": "OLD"}),
            _resp(401, url, json={"error": "invalid_token"}),
            _resp(200, c.token_url, json={"access_token": "NEW"}),
            _resp(201, url, json={"ticket": {"id": 7}}),
        ]
    )

    with patcher, patch("app.modules.integration.zendesk.tracer", fake_tracer):
        result = await c.create_ticket(subject="s", description="d")

    assert result == {"status": 200, "data": {"ticket": {"id": 7}}}
    assert span.error == 0
    span.set_tag.assert_not_called()


@pytest.mark.asyncio
async def test_create_ticket_network_error_marks_span_failed():
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )
    fake_tracer, span, request_span = _tracer_with_span()

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    with patch("app.modules.integration.zendesk.httpx.AsyncClient", _FailingClient), patch(
        "app.modules.integration.zendesk.tracer", fake_tracer
    ):
        assert await c.create_ticket(subject="s", description="d") is None

    assert span.error == 1
    span.set_tag.assert_any_call("zendesk.error", "network_error")
    # Zendesk never answered, so no status code (the 500 is our own placeholder).
    assert not any(
        call.args[0] == "zendesk.status_code" for call in span.set_tag.call_args_list
    )
    assert request_span.error == 0


@pytest.mark.asyncio
async def test_network_error_log_has_no_traceback_locals(caplog):
    """The network-error log carries no traceback, whose locals hold the payload."""
    c = ZendeskConnector(
        subdomain="acme", email="a@b.com", api_token="tok", auth_method="api_token"
    )

    class _FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    with patch("app.modules.integration.zendesk.httpx.AsyncClient", _FailingClient):
        await c.create_ticket(
            subject="s", description="d", requester_email="john@example.com"
        )

    records = [r for r in caplog.records if "network error" in r.getMessage()]
    assert records and all(r.exc_info is None for r in records)
    assert "ConnectError: connection refused" in records[0].getMessage()
    assert "john@example.com" not in caplog.text
