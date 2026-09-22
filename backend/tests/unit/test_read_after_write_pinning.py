"""Unit tests for the read-your-writes guard: a client that just wrote keeps reading from the writer"""

import base64
import hashlib
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.config.settings import settings
from app.core.tenant_scope import clear_tenant_context, set_tenant_context
from app.db.read_routing import allow_replica_reads, reads_pinned_to_writer, reset_replica_reads
from app.middlewares import read_after_write_middleware as guard_module
from app.middlewares.read_after_write_middleware import ReadAfterWriteMiddleware

PIN_SECONDS = 5


class FakeRedis:
    def __init__(self):
        self.present = False
        self.failing = False
        self.exists_calls = []
        self.set_calls = []

    async def exists(self, key):
        if self.failing:
            raise ConnectionError("redis down")
        self.exists_calls.append(key)
        return 1 if self.present else 0

    async def set(self, key, value, ex=None):
        if self.failing:
            raise ConnectionError("redis down")
        self.set_calls.append((key, value, ex))


def _expected_key(tenant="master", user_id="user-1", api_key=None):
    identity = f"key\x00{api_key}" if api_key else f"user\x00{user_id}"
    scope = f"{tenant}\x00{identity}".encode()
    return f"read-pin:{hashlib.sha256(scope).hexdigest()[:32]}"


def _bearer(user_id="user-1"):
    payload = base64.urlsafe_b64encode(json.dumps({"user_id": user_id, "sub": "admin"}).encode()).rstrip(b"=")
    return {"Authorization": f"Bearer header.{payload.decode()}.signature"}


@pytest.fixture
def guarded_app(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(guard_module, "_redis", lambda: redis)
    monkeypatch.setattr(settings, "DB_READ_HOST", "reader.internal")
    monkeypatch.setattr(settings, "DB_READ_PIN_AFTER_WRITE_SECONDS", PIN_SECONDS)

    app = FastAPI()
    app.add_middleware(ReadAfterWriteMiddleware)

    @app.get("/read")
    async def read():
        return {"pinned": reads_pinned_to_writer()}

    @app.post("/write")
    async def write():
        return {"ok": True}

    @app.post("/write-fails")
    async def write_fails():
        raise HTTPException(status_code=400)

    return TestClient(app), redis


def test_read_without_a_recent_write_uses_the_replica(guarded_app):
    client, redis = guarded_app
    assert client.get("/read", headers=_bearer()).json() == {"pinned": False}
    assert redis.exists_calls == [_expected_key()]


def test_successful_write_pins_the_client_for_the_configured_window(guarded_app):
    client, redis = guarded_app
    assert client.post("/write", headers=_bearer()).status_code == 200
    assert redis.set_calls == [(_expected_key(), "1", PIN_SECONDS)]


def test_failed_write_does_not_pin(guarded_app):
    client, redis = guarded_app
    assert client.post("/write-fails", headers=_bearer()).status_code == 400
    assert redis.set_calls == []


def test_read_after_a_recent_write_is_served_by_the_writer(guarded_app):
    client, redis = guarded_app
    redis.present = True
    assert client.get("/read", headers=_bearer()).json() == {"pinned": True}


def test_redis_failure_fails_safe_to_the_writer(guarded_app):
    client, redis = guarded_app
    redis.failing = True
    assert client.get("/read", headers=_bearer()).json() == {"pinned": True}
    assert client.post("/write", headers=_bearer()).status_code == 200


def test_requests_without_an_identity_are_not_tracked(guarded_app):
    client, redis = guarded_app
    assert client.get("/read").json() == {"pinned": False}
    assert client.post("/write").status_code == 200
    assert redis.exists_calls == [] and redis.set_calls == []


def test_api_key_clients_are_pinned_after_their_own_write(guarded_app):
    """GET /conversations and its write siblings both accept an API key, so an API-key
    client can write and list. It needs the same read-your-writes guarantee."""
    client, redis = guarded_app
    key = _expected_key(api_key="agent-secret")

    assert client.post("/write", headers={"x-api-key": "agent-secret"}).status_code == 200
    assert redis.set_calls == [(key, "1", PIN_SECONDS)]

    redis.present = True
    assert client.get("/read", headers={"x-api-key": "agent-secret"}).json() == {"pinned": True}
    assert redis.exists_calls == [key]


def test_each_api_key_gets_its_own_pin(guarded_app):
    client, redis = guarded_app
    client.post("/write", headers={"x-api-key": "key-one"})
    client.post("/write", headers={"x-api-key": "key-two"})
    written = [call[0] for call in redis.set_calls]
    assert written == [_expected_key(api_key="key-one"), _expected_key(api_key="key-two")]


def test_the_raw_api_key_never_reaches_redis(guarded_app):
    client, redis = guarded_app
    client.post("/write", headers={"x-api-key": "agent-secret"})
    assert "agent-secret" not in redis.set_calls[0][0]


def test_a_bearer_token_wins_over_an_api_key_the_way_auth_resolves_them(guarded_app):
    """get_current_user only looks at the API key when there is no bearer token, so a
    request carrying both must pin under the user. Grouping it under the key would put
    that user's other requests on a different pin and lose the guarantee."""
    client, redis = guarded_app
    both = {**_bearer("user-1"), "x-api-key": "agent-secret"}
    client.post("/write", headers=both)
    assert redis.set_calls == [(_expected_key(user_id="user-1"), "1", PIN_SECONDS)]


def test_an_unparseable_bearer_does_not_fall_through_to_the_api_key(guarded_app):
    """auth would reject this request outright, so there is no identity to group under."""
    client, redis = guarded_app
    client.post("/write", headers={"Authorization": "Bearer nope", "x-api-key": "agent-secret"})
    assert redis.set_calls == []


def test_an_api_key_and_a_user_id_with_the_same_value_do_not_share_a_pin(guarded_app):
    client, redis = guarded_app
    client.post("/write", headers={"x-api-key": "shared-value"})
    client.post("/write", headers=_bearer("shared-value"))
    assert redis.set_calls[0][0] != redis.set_calls[1][0]


@pytest.mark.parametrize(
    "payload,decodes_to",
    [
        ("W10", "list"),
        ("MQ", "int"),
        ("ImFiYyI", "string"),
        ("bnVsbA", "null"),
        ("!!!", "garbage"),
        (base64.urlsafe_b64encode(b"[" * 20000).rstrip(b"=").decode(), "deeply nested json"),
    ],
)
def test_malformed_bearer_payloads_are_ignored_rather_than_crashing(guarded_app, payload, decodes_to):
    client, redis = guarded_app
    response = client.get("/read", headers={"Authorization": f"Bearer header.{payload}.signature"})
    assert response.status_code == 200, decodes_to
    assert response.json() == {"pinned": False}
    assert redis.exists_calls == []


def test_pin_keys_are_separated_by_tenant(guarded_app):
    client, redis = guarded_app
    set_tenant_context("acme-co")
    try:
        client.post("/write", headers=_bearer())
    finally:
        clear_tenant_context()
    assert redis.set_calls == [(_expected_key(tenant="acme-co"), "1", PIN_SECONDS)]


def test_guard_is_inactive_without_a_replica(guarded_app, monkeypatch):
    client, redis = guarded_app
    monkeypatch.setattr(settings, "DB_READ_HOST", None)
    client.get("/read", headers=_bearer())
    client.post("/write", headers=_bearer())
    assert redis.exists_calls == [] and redis.set_calls == []


def test_guard_is_inactive_when_the_window_is_zero(guarded_app, monkeypatch):
    client, redis = guarded_app
    monkeypatch.setattr(settings, "DB_READ_PIN_AFTER_WRITE_SECONDS", 0)
    client.get("/read", headers=_bearer())
    client.post("/write", headers=_bearer())
    assert redis.exists_calls == [] and redis.set_calls == []


@pytest.mark.asyncio
async def test_pin_is_released_when_the_request_finishes(monkeypatch):
    """A leaked pin would quietly route every later read on this worker to the writer."""
    redis = FakeRedis()
    redis.present = True
    monkeypatch.setattr(guard_module, "_redis", lambda: redis)
    middleware = ReadAfterWriteMiddleware(app=None)
    seen_inside = []

    async def call_next(_request):
        seen_inside.append(reads_pinned_to_writer())
        return "response"

    assert await middleware._serve_read(None, call_next, _expected_key()) == "response"
    assert seen_inside == [True]
    assert reads_pinned_to_writer() is False


@pytest.mark.asyncio
async def test_pin_is_released_even_when_the_endpoint_raises(monkeypatch):
    redis = FakeRedis()
    redis.present = True
    monkeypatch.setattr(guard_module, "_redis", lambda: redis)
    middleware = ReadAfterWriteMiddleware(app=None)

    async def call_next(_request):
        raise RuntimeError("endpoint exploded")

    with pytest.raises(RuntimeError):
        await middleware._serve_read(None, call_next, _expected_key())
    assert reads_pinned_to_writer() is False


def test_provider_returns_the_write_session_while_pinned(monkeypatch):
    from app.db import read_routing
    from app.dependencies.dependency_injection import Dependencies

    monkeypatch.setattr(settings, "DB_READ_HOST", "reader.internal")
    write_session = object()
    scope_token = allow_replica_reads()
    pin_token = read_routing.pin_reads_to_writer()
    set_tenant_context("acme-co")
    try:
        assert Dependencies().provide_read_session(write_session) is write_session
    finally:
        read_routing.unpin_reads(pin_token)
        reset_replica_reads(scope_token)
        clear_tenant_context()


def test_pin_keys_are_a_fixed_length_digest_of_caller_supplied_values():
    """Tenant and subject both come from the request, so the key must not grow with
    them and two different pairs must not collide."""
    from app.middlewares.read_after_write_middleware import _client_key

    class FakeRequest:
        """Real request headers are case-insensitive; a plain dict is not."""

        def __init__(self, headers):
            self.headers = {key.lower(): value for key, value in headers.items()}

    normal = _client_key(FakeRequest(_bearer("user-1")))
    assert len(_client_key(FakeRequest(_bearer("u" * 1000)))) == len(normal)
    assert len(_client_key(FakeRequest({"x-api-key": "k" * 1000}))) == len(normal)

    set_tenant_context("a")
    try:
        ambiguous = _client_key(FakeRequest(_bearer("b:c")))
    finally:
        clear_tenant_context()
    set_tenant_context("a:b")
    try:
        other = _client_key(FakeRequest(_bearer("c")))
    finally:
        clear_tenant_context()
    assert ambiguous != other
