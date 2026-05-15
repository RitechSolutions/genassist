"""Unit tests for Microsoft Entra OIDC helpers."""

import pytest

from app.core.sso.microsoft_entra_oidc import (
    build_authorize_url,
    claims_email,
    claims_entra_oid,
    exchange_authorization_code,
    generate_pkce_pair,
)


def test_generate_pkce_pair_lengths():
    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 40
    assert len(challenge) >= 40


def test_build_authorize_url_contains_expected_query():
    url = build_authorize_url(
        entra_tenant_segment="11111111-1111-1111-1111-111111111111",
        client_id="myclient",
        redirect_uri="https://app/callback",
        state="stateval",
        nonce="nonceval",
        code_challenge="challengex",
    )
    assert "11111111-1111-1111-1111-111111111111" in url
    assert "client_id=myclient" in url
    assert "code_challenge=challengex" in url
    assert "nonce=nonceval" in url


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"email": "A@B.COM"}, "a@b.com"),
        ({"preferred_username": "x@y.org"}, "x@y.org"),
        ({}, None),
        ({"email": "not-an-email"}, None),
    ],
)
def test_claims_email(payload, expected):
    assert claims_email(payload) == expected


def test_claims_entra_oid_prefers_oid():
    assert claims_entra_oid({"oid": "abc", "sub": "def"}) == "abc"
    assert claims_entra_oid({"sub": "solo"}) == "solo"


@pytest.mark.asyncio
async def test_exchange_authorization_code_with_custom_client():
    class Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"id_token": "x.y.z", "access_token": "at"}

    class FakeClient:
        async def post(self, *args, **kwargs):
            return Resp()

    out = await exchange_authorization_code(
        entra_tenant_segment="tid",
        client_id="c",
        client_secret="s",
        redirect_uri="https://r",
        code="code",
        code_verifier="v",
        client=FakeClient(),
    )
    assert out["id_token"] == "x.y.z"
    assert out["access_token"] == "at"
