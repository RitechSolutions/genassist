"""Webhook Trigger ingress: authentication helpers and the delivery pipeline.

The service's DB collaborators are replaced with in-memory fakes so the tests
cover the ordering and status codes of the pipeline, not SQLAlchemy.
"""

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.utils.encryption_utils import encrypt_key
from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.services.workflow_trigger import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WorkflowTriggerService,
    build_public_url,
    compute_signature,
    find_trigger_node,
    parse_body,
    verify_bearer,
    verify_hmac,
)

SECRET = "s3cr3t-token"


class TestAuthHelpers:
    def test_bearer_requires_scheme_and_exact_token(self):
        assert verify_bearer(f"Bearer {SECRET}", SECRET)
        assert verify_bearer(f"bearer {SECRET}", SECRET)
        assert not verify_bearer(SECRET, SECRET)
        assert not verify_bearer("Bearer nope", SECRET)
        assert not verify_bearer(None, SECRET)
        assert not verify_bearer("Basic abc", SECRET)

    def test_hmac_accepts_fresh_valid_signature(self):
        body = b'{"a":1}'
        ts = str(int(time.time()))
        headers = {TIMESTAMP_HEADER: ts, SIGNATURE_HEADER: compute_signature(SECRET, ts, body)}
        assert verify_hmac(headers, body, SECRET, 300) == (True, "")

    def test_hmac_rejects_stale_missing_and_tampered(self):
        body = b'{"a":1}'
        ts = str(int(time.time()) - 1000)
        headers = {TIMESTAMP_HEADER: ts, SIGNATURE_HEADER: compute_signature(SECRET, ts, body)}
        ok, reason = verify_hmac(headers, body, SECRET, 300)
        assert not ok and "window" in reason

        assert verify_hmac({}, body, SECRET, 300)[0] is False

        ts = str(int(time.time()))
        headers = {TIMESTAMP_HEADER: ts, SIGNATURE_HEADER: compute_signature(SECRET, ts, b"other")}
        assert verify_hmac(headers, body, SECRET, 300) == (False, "Signature mismatch")

        headers = {TIMESTAMP_HEADER: "abc", SIGNATURE_HEADER: "sha256=00"}
        assert verify_hmac(headers, body, SECRET, 300)[1] == "Invalid timestamp"


def test_parse_body_json_text_and_empty():
    assert parse_body(b"") == {}
    assert parse_body(b'{"a": 1}') == {"a": 1}
    assert parse_body(b"plain") == {"raw": "plain"}


def test_find_trigger_node_matches_id_and_type():
    nodes = [{"id": "n1", "type": "chatInputNode"}, {"id": "n2", "type": "webhookTriggerNode"}]
    assert find_trigger_node(nodes, "n2")["id"] == "n2"
    assert find_trigger_node(nodes, "n1") is None
    assert find_trigger_node(None, "n2") is None


def test_public_url_uses_frontend_base_and_carries_tenant():
    with patch("app.services.workflow_trigger.get_tenant_context", return_value="acme"):
        url = build_public_url("https://host/api", None, "abc", "POST")
    assert url == "https://host/api/webhook/execute/abc?x-tenant-id=acme"


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #

class _FakeRunRepo:
    def __init__(self):
        self.runs = []
        self.db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())

    async def get_by_idempotency_key(self, webhook_id, key):
        return next((r for r in self.runs if r.webhook_id == webhook_id and r.idempotency_key == key), None)

    async def create(self, **kwargs):
        run = SimpleNamespace(id=uuid4(), status=WorkflowScheduleRunStatus.PENDING, **kwargs)
        self.runs.append(run)
        return run

    async def get_last_run(self, webhook_id):
        return None

    async def update_status(self, *a, **k):
        return None


def _service(agent):
    service = WorkflowTriggerService(
        webhook_repository=MagicMock(),
        run_repository=_FakeRunRepo(),
        agent_repository=SimpleNamespace(get_by_id_full=AsyncMock(return_value=agent)),
    )
    service._dispatch = AsyncMock()
    service._within_rate_limit = AsyncMock(return_value=True)
    return service


def _agent(node_data=None, active=1):
    node = {"id": "wt", "type": "webhookTriggerNode", "data": node_data or {}}
    workflow = SimpleNamespace(id=uuid4(), nodes=[node], edges=[])
    return SimpleNamespace(id=uuid4(), is_active=active, workflow=workflow)


def _webhook(agent, **overrides):
    values = dict(
        id=uuid4(), agent_id=agent.id, node_id="wt", method="POST", auth_mode="bearer",
        secret=encrypt_key(SECRET), is_active=1, is_deleted=0, rate_limit_per_minute=60,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _request(body=b"{}", headers=None, method="POST", query=None):
    return SimpleNamespace(
        method=method,
        headers={"authorization": f"Bearer {SECRET}", **(headers or {})},
        query_params=query or {"x-tenant-id": "acme"},
        app=None,
    )


@pytest.mark.asyncio
async def test_valid_delivery_queues_a_run_and_answers_202():
    agent = _agent({"messagePath": "body.text", "fieldMappings": [{"key": "order_id", "path": "body.id"}]})
    service = _service(agent)
    webhook = _webhook(agent)
    body = json.dumps({"id": 5, "text": "hello"}).encode()

    response = await service.handle_delivery(webhook, _request(body), body, "acme")

    assert response.status_code == 202
    payload = json.loads(response.body)
    assert payload["status"] == "pending" and payload["duplicate"] is False
    run = service.run_repository.runs[0]
    assert run.input_data["order_id"] == 5
    assert run.input_data["message"] == "hello"
    assert run.input_data["thread_id"] == payload["thread_id"]
    assert run.input_data["webhook"]["headers"].get("authorization") is None  # credentials never stored
    assert "x-tenant-id" not in run.input_data["webhook"]["query"]
    service.run_repository.db.commit.assert_awaited()
    service._dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_rejections_in_order():
    agent = _agent()
    service = _service(agent)

    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent, is_active=0), _request(), b"{}", "acme")
    assert e.value.status_code == 404

    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent), _request(method="GET"), b"{}", "acme")
    assert e.value.status_code == 405

    with patch("app.services.workflow_trigger.settings.WEBHOOK_TRIGGER_MAX_BODY_BYTES", 4):
        with pytest.raises(HTTPException) as e:
            await service.handle_delivery(_webhook(agent), _request(), b"{...}", "acme")
    assert e.value.status_code == 413

    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent), _request(headers={"authorization": "Bearer no"}), b"{}", "acme")
    assert e.value.status_code == 401

    service._within_rate_limit = AsyncMock(return_value=False)
    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent), _request(), b"{}", "acme")
    assert e.value.status_code == 429
    assert service.run_repository.runs == []


@pytest.mark.asyncio
async def test_undecryptable_secret_fails_closed():
    agent = _agent()
    service = _service(agent)
    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent, secret="not-fernet"), _request(), b"{}", "acme")
    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_hmac_mode_verifies_signature_over_raw_body():
    agent = _agent()
    service = _service(agent)
    webhook = _webhook(agent, auth_mode="hmac")
    body = b'{"x": 1}'
    ts = str(int(time.time()))
    request = _request(body, headers={TIMESTAMP_HEADER: ts, SIGNATURE_HEADER: compute_signature(SECRET, ts, body)})
    request.headers.pop("authorization")
    response = await service.handle_delivery(webhook, request, body, "acme")
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_node_not_in_published_workflow_and_deactivated():
    agent = _agent()
    service = _service(agent)
    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent, node_id="missing"), _request(), b"{}", "acme")
    assert e.value.status_code == 404

    agent = _agent({"deactivated": True})
    service = _service(agent)
    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent), _request(), b"{}", "acme")
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_mapping_failure_is_422_and_creates_no_run():
    agent = _agent({"fieldMappings": [{"key": "order_id", "path": "body.id", "required": True}]})
    service = _service(agent)
    with pytest.raises(HTTPException) as e:
        await service.handle_delivery(_webhook(agent), _request(), b"{}", "acme")
    assert e.value.status_code == 422
    assert "order_id" in e.value.detail["errors"][0]
    assert service.run_repository.runs == []


@pytest.mark.asyncio
async def test_idempotent_redelivery_returns_first_run_with_200():
    agent = _agent()
    service = _service(agent)
    webhook = _webhook(agent)
    headers = {"idempotency-key": "evt_1"}

    first = await service.handle_delivery(webhook, _request(headers=headers), b"{}", "acme")
    second = await service.handle_delivery(webhook, _request(headers=headers), b"{}", "acme")

    assert first.status_code == 202 and second.status_code == 200
    assert json.loads(second.body)["run_id"] == json.loads(first.body)["run_id"]
    assert json.loads(second.body)["duplicate"] is True
    assert len(service.run_repository.runs) == 1
    service._dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_thread_id_path_groups_deliveries():
    agent = _agent({"threadIdPath": "body.conversation_id"})
    service = _service(agent)
    body = b'{"conversation_id": "conv-7"}'
    response = await service.handle_delivery(_webhook(agent), _request(body), body, "acme")
    assert json.loads(response.body)["thread_id"] == "conv-7"
