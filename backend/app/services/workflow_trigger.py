"""Webhook Trigger endpoints: management API and public ingress.

A trigger is a ``webhooks`` row of type ``workflow_trigger`` bound to an agent
and a Webhook Trigger node id. It never pins a workflow version: every
delivery resolves the agent's *current* workflow (like schedules), checks the
node is still part of it, maps the payload and queues a run on the ``ml``
queue. The public route answers 202 with the run id.

Ingress pipeline (fail closed, in this order): active → method → body size →
auth (bearer or HMAC, constant-time) → rate limit → parse → agent/workflow/node
→ mapping (422) → idempotency → PENDING run → commit → dispatch → 202.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from injector import inject
from sqlalchemy.exc import IntegrityError

from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.tenant_scope import get_tenant_context
from app.core.utils.encryption_utils import decrypt_key, encrypt_key
from app.core.utils.enums.workflow_schedule_enum import WorkflowScheduleRunStatus
from app.db.models.webhook import WebhookAuthMode, WebhookModel, WebhookType
from app.modules.workflow.webhook_trigger_mapping import (
    build_envelope,
    build_trigger_input,
    extract_idempotency_key,
    parse_sample_payload,
    resolve_thread_id,
)
from app.repositories.agent import AgentRepository
from app.repositories.webhook_repository import WebhookRepository
from app.repositories.workflow_trigger_run import WorkflowTriggerRunRepository
from app.schemas.workflow_trigger import (
    WorkflowTriggerDeliveryResponse,
    WorkflowTriggerProvision,
    WorkflowTriggerProvisionResponse,
    WorkflowTriggerRead,
    WorkflowTriggerRunRead,
    WorkflowTriggerRunSummary,
    WorkflowTriggerSecret,
    WorkflowTriggerTestRequest,
    WorkflowTriggerUpdate,
)

logger = logging.getLogger(__name__)

TRIGGER_NODE_TYPE = "webhookTriggerNode"
TRIGGER_TASK_NAME = "execute_webhook_trigger_run"
SIGNATURE_HEADER = "x-genassist-signature"
TIMESTAMP_HEADER = "x-genassist-timestamp"

# Never persisted into a run's input (they carry the caller's credentials).
_STRIPPED_HEADERS = {"authorization", "cookie", "set-cookie", SIGNATURE_HEADER, "proxy-authorization"}


# ---------------------------------------------------------------------------
# Pure helpers (unit-testable without a DB)
# ---------------------------------------------------------------------------

def trigger_name(agent_id: UUID, node_id: str) -> str:
    return f"workflow-trigger:{agent_id}:{node_id}"


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


def compute_signature(secret: str, timestamp: str, body: bytes) -> str:
    """``sha256=<hex>`` over ``"{timestamp}.{raw body}"``."""
    mac = hmac.new(secret.encode("utf-8"), timestamp.encode("utf-8") + b"." + body, hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def verify_bearer(authorization: Optional[str], secret: str) -> bool:
    if not authorization:
        return False
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return False
    return hmac.compare_digest(token.strip(), secret)


def verify_hmac(
    headers: Dict[str, str],
    body: bytes,
    secret: str,
    tolerance_seconds: int,
    now: Optional[float] = None,
) -> Tuple[bool, str]:
    """Check the signature header against the body and reject stale timestamps."""
    lowered = {str(k).lower(): v for k, v in headers.items()}
    timestamp = lowered.get(TIMESTAMP_HEADER)
    signature = lowered.get(SIGNATURE_HEADER)
    if not timestamp or not signature:
        return False, "Missing signature headers"
    try:
        ts = int(float(timestamp))
    except ValueError:
        return False, "Invalid timestamp"
    current = now if now is not None else time.time()
    if abs(current - ts) > tolerance_seconds:
        return False, "Timestamp outside the allowed window"
    expected = compute_signature(secret, timestamp, body)
    if not hmac.compare_digest(signature.strip(), expected):
        return False, "Signature mismatch"
    return True, ""


def find_trigger_node(workflow_nodes: Optional[List[dict]], node_id: str) -> Optional[dict]:
    for node in workflow_nodes or []:
        if node.get("id") == node_id and node.get("type") == TRIGGER_NODE_TYPE:
            return node
    return None


def parse_body(raw: bytes) -> Any:
    if not raw or not raw.strip():
        return {}
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except ValueError:
        return {"raw": text}


def build_public_url(base_url: Optional[str], request: Optional[Request], webhook_id: UUID, method: str) -> str:
    """Same shape as the existing webhook feature: ``{api}/webhook/execute/{id}?x-tenant-id=<slug>``."""
    if base_url:
        base = base_url if base_url.endswith("/") else base_url + "/"
        url = f"{base}webhook/execute/{webhook_id}"
    elif request is not None:
        url = str(
            request.url_for(
                "webhook_handler_post" if method == "POST" else "webhook_handler_get",
                webhook_id=str(webhook_id),
            )
        )
    else:
        base = settings.APP_URL or ""
        base = base if base.endswith("/") else base + "/"
        url = f"{base}api/webhook/execute/{webhook_id}"
    tenant_param = {settings.TENANT_HEADER_NAME.lower(): get_tenant_context()}
    return f"{url}?{urlencode(tenant_param)}"


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

@inject
class WorkflowTriggerService:
    def __init__(
        self,
        webhook_repository: WebhookRepository,
        run_repository: WorkflowTriggerRunRepository,
        agent_repository: AgentRepository,
    ):
        self.webhook_repository = webhook_repository
        self.run_repository = run_repository
        self.agent_repository = agent_repository

    # ----- management -----------------------------------------------------

    async def _get_trigger(self, trigger_id: UUID) -> WebhookModel:
        webhook = await self.webhook_repository.get_by_id(trigger_id)
        if not webhook or webhook.webhook_type != WebhookType.WORKFLOW_TRIGGER.value:
            raise AppException(error_key=ErrorKey.NOT_FOUND, error_detail="Webhook trigger not found")
        return webhook

    async def _to_read(self, webhook: WebhookModel) -> WorkflowTriggerRead:
        read = WorkflowTriggerRead(
            id=webhook.id,
            agent_id=webhook.agent_id,
            node_id=webhook.node_id,
            url=webhook.url,
            method=webhook.method,
            auth_mode=webhook.auth_mode or WebhookAuthMode.BEARER.value,
            rate_limit_per_minute=webhook.rate_limit_per_minute or 0,
            is_active=bool(webhook.is_active),
            created_at=webhook.created_at,
            updated_at=webhook.updated_at,
        )
        last_run = await self.run_repository.get_last_run(webhook.id)
        if last_run:
            read.last_run_status = last_run.status
            read.last_run_at = last_run.created_at
        return read

    async def provision(
        self, data: WorkflowTriggerProvision, request: Optional[Request] = None
    ) -> WorkflowTriggerProvisionResponse:
        """Idempotent: returns the existing endpoint, or creates one and returns its secret once."""
        existing = await self.webhook_repository.get_trigger_by_agent_node(data.agent_id, data.node_id)
        if existing:
            read = await self._to_read(existing)
            return WorkflowTriggerProvisionResponse(**read.model_dump(), secret=None, created=False)

        agent = await self.agent_repository.get_by_id(data.agent_id)
        if not agent:
            raise AppException(error_key=ErrorKey.NOT_FOUND, error_detail="Agent not found")

        webhook_id = uuid4()
        plain_secret = generate_secret()
        webhook = WebhookModel(
            id=webhook_id,
            name=trigger_name(data.agent_id, data.node_id),
            url=build_public_url(data.base_url, request, webhook_id, "POST"),
            method="POST",
            headers={},
            secret=encrypt_key(plain_secret),
            description="Endpoint of a Webhook Trigger workflow node",
            is_active=1,
            webhook_type=WebhookType.WORKFLOW_TRIGGER.value,
            agent_id=data.agent_id,
            node_id=data.node_id,
            auth_mode=WebhookAuthMode.BEARER.value,
            rate_limit_per_minute=60,
        )
        webhook = await self.webhook_repository.create_model(webhook)
        read = await self._to_read(webhook)
        return WorkflowTriggerProvisionResponse(**read.model_dump(), secret=plain_secret, created=True)

    async def list_by_agent(self, agent_id: UUID) -> List[WorkflowTriggerRead]:
        triggers = await self.webhook_repository.list_triggers_by_agent(agent_id)
        return [await self._to_read(t) for t in triggers]

    async def get(self, trigger_id: UUID) -> WorkflowTriggerRead:
        return await self._to_read(await self._get_trigger(trigger_id))

    async def update(self, trigger_id: UUID, data: WorkflowTriggerUpdate) -> WorkflowTriggerRead:
        webhook = await self._get_trigger(trigger_id)
        changes = data.model_dump(exclude_unset=True)
        if "method" in changes and changes["method"]:
            webhook.method = changes["method"]
            # The URL is method-agnostic on the execute route; keep it as is.
        if "auth_mode" in changes and changes["auth_mode"]:
            webhook.auth_mode = changes["auth_mode"]
        if "rate_limit_per_minute" in changes and changes["rate_limit_per_minute"] is not None:
            webhook.rate_limit_per_minute = int(changes["rate_limit_per_minute"])
        if "is_active" in changes and changes["is_active"] is not None:
            webhook.is_active = 1 if changes["is_active"] else 0
        webhook = await self.webhook_repository.save(webhook)
        return await self._to_read(webhook)

    async def delete(self, trigger_id: UUID) -> None:
        webhook = await self._get_trigger(trigger_id)
        await self.webhook_repository.delete(webhook.id)

    async def rotate_secret(self, trigger_id: UUID) -> WorkflowTriggerSecret:
        webhook = await self._get_trigger(trigger_id)
        plain_secret = generate_secret()
        webhook.secret = encrypt_key(plain_secret)
        await self.webhook_repository.save(webhook)
        return WorkflowTriggerSecret(secret=plain_secret, auth_mode=webhook.auth_mode or "bearer")

    async def reveal_secret(self, trigger_id: UUID) -> WorkflowTriggerSecret:
        webhook = await self._get_trigger(trigger_id)
        secret = self._decrypt_secret(webhook)
        if not secret:
            raise AppException(
                error_key=ErrorKey.INTERNAL_ERROR,
                error_detail="The stored secret cannot be decrypted; rotate it.",
            )
        return WorkflowTriggerSecret(secret=secret, auth_mode=webhook.auth_mode or "bearer")

    async def list_runs(
        self,
        trigger_id: UUID,
        status: Optional[WorkflowScheduleRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowTriggerRunSummary]:
        webhook = await self._get_trigger(trigger_id)
        runs = await self.run_repository.list_by_webhook(webhook.id, status=status, limit=limit, offset=offset)
        return [WorkflowTriggerRunSummary.model_validate(r) for r in runs]

    async def get_run(self, trigger_id: UUID, run_id: UUID) -> WorkflowTriggerRunRead:
        webhook = await self._get_trigger(trigger_id)
        run = await self.run_repository.get_by_id(run_id)
        if run.webhook_id != webhook.id:
            raise AppException(error_key=ErrorKey.NOT_FOUND, error_detail="Run not found")
        return WorkflowTriggerRunRead.model_validate(run)

    async def test(
        self, trigger_id: UUID, data: WorkflowTriggerTestRequest, request: Optional[Request] = None
    ) -> WorkflowTriggerDeliveryResponse:
        """Queue a real run from the builder, bypassing auth, rate limit and idempotency."""
        webhook = await self._get_trigger(trigger_id)
        agent, workflow, node = await self._resolve_trigger_node(webhook)
        node_data = node.get("data") or {}
        body = data.payload if data.payload is not None else parse_sample_payload(node_data)
        envelope = build_envelope(
            method=webhook.method or "POST",
            headers=data.headers or {},
            query=data.query or {},
            body=body,
            is_test=True,
        )
        response, _ = await self._start_run(
            webhook, agent, workflow, node, envelope, request, idempotency_key=None
        )
        return response

    # ----- public ingress -------------------------------------------------

    async def handle_delivery(
        self,
        webhook: WebhookModel,
        request: Request,
        raw_body: bytes,
        tenant_id: Optional[str],
    ) -> JSONResponse:
        tenant_id = tenant_id or get_tenant_context() or "master"

        if int(webhook.is_active or 0) != 1 or int(webhook.is_deleted or 0) != 0:
            raise HTTPException(status_code=404, detail="Webhook not found")
        if request.method != (webhook.method or "POST"):
            raise HTTPException(status_code=405, detail=f"Use {webhook.method} for this endpoint")
        if len(raw_body) > settings.WEBHOOK_TRIGGER_MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload too large")

        self._authenticate(webhook, request, raw_body)

        if not await self._within_rate_limit(webhook, tenant_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded for this endpoint")

        agent, workflow, node = await self._resolve_trigger_node(webhook)

        query = {
            k: v for k, v in request.query_params.items()
            if k.lower() != settings.TENANT_HEADER_NAME.lower()
        }
        headers = {k.lower(): v for k, v in request.headers.items() if k.lower() not in _STRIPPED_HEADERS}
        envelope = build_envelope(
            method=request.method, headers=headers, query=query, body=parse_body(raw_body)
        )
        idempotency_key = extract_idempotency_key(envelope, node.get("data") or {})

        response, status_code = await self._start_run(
            webhook, agent, workflow, node, envelope, request, idempotency_key=idempotency_key
        )
        return JSONResponse(status_code=status_code, content=json.loads(response.model_dump_json()))

    # ----- internals ------------------------------------------------------

    def _decrypt_secret(self, webhook: WebhookModel) -> Optional[str]:
        stored = webhook.secret
        if not stored:
            return None
        decrypted = decrypt_key(str(stored))
        # decrypt_key returns the ciphertext unchanged when it cannot decrypt.
        if not decrypted or decrypted == stored:
            return None
        return decrypted

    def _authenticate(self, webhook: WebhookModel, request: Request, raw_body: bytes) -> None:
        secret = self._decrypt_secret(webhook)
        if not secret:
            logger.error("Webhook trigger %s has no usable secret; rejecting delivery", webhook.id)
            raise HTTPException(status_code=401, detail="Endpoint is not accepting deliveries")
        mode = webhook.auth_mode or WebhookAuthMode.BEARER.value
        if mode == WebhookAuthMode.HMAC.value:
            ok, reason = verify_hmac(
                dict(request.headers), raw_body, secret, settings.WEBHOOK_TRIGGER_HMAC_TOLERANCE_SECONDS
            )
            if not ok:
                raise HTTPException(status_code=401, detail=reason or "Invalid signature")
        elif not verify_bearer(request.headers.get("authorization"), secret):
            raise HTTPException(status_code=401, detail="Invalid or missing bearer token")

    async def _within_rate_limit(self, webhook: WebhookModel, tenant_id: str) -> bool:
        """Per-endpoint one-minute window in Redis; degrades open if Redis is down."""
        limit = int(webhook.rate_limit_per_minute or 0)
        if limit <= 0:
            return True
        key = f"wftrigger:rl:{tenant_id}:{webhook.id}:{int(time.time() // 60)}"
        try:
            from app.dependencies.dependency_injection import RedisString
            from app.dependencies.injector import injector

            redis = injector.get(RedisString)
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 120)
            return count <= limit
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Webhook trigger rate-limit check degraded open: %s", exc)
            return True

    async def _resolve_trigger_node(self, webhook: WebhookModel):
        """The agent's current workflow and the trigger node inside it."""
        agent = await self.agent_repository.get_by_id_full(webhook.agent_id) if webhook.agent_id else None
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        if int(agent.is_active or 0) != 1:
            raise HTTPException(status_code=409, detail="Agent is inactive")
        workflow = agent.workflow
        if not workflow:
            raise HTTPException(status_code=409, detail="Agent has no published workflow")
        node = find_trigger_node(workflow.nodes, webhook.node_id or "")
        if not node:
            raise HTTPException(
                status_code=404,
                detail="Trigger node is not part of the agent's published workflow. Save the workflow first.",
            )
        if (node.get("data") or {}).get("deactivated"):
            raise HTTPException(status_code=409, detail="Trigger node is deactivated")
        return agent, workflow, node

    async def _start_run(
        self,
        webhook: WebhookModel,
        agent,
        workflow,
        node: dict,
        envelope: Dict[str, Any],
        request: Optional[Request],
        idempotency_key: Optional[str],
    ) -> Tuple[WorkflowTriggerDeliveryResponse, int]:
        node_data = node.get("data") or {}
        input_data, errors = build_trigger_input(envelope, node_data)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"message": "Payload does not match the trigger's field mapping", "errors": errors},
            )
        thread_id = resolve_thread_id(envelope, node_data) or str(uuid4())
        input_data["thread_id"] = thread_id

        if idempotency_key:
            existing = await self.run_repository.get_by_idempotency_key(webhook.id, idempotency_key)
            if existing:
                return self._delivery_response(existing, duplicate=True), 200

        try:
            run = await self.run_repository.create(
                webhook_id=webhook.id,
                agent_id=agent.id,
                node_id=node["id"],
                workflow_id=workflow.id,
                thread_id=thread_id,
                input_data=input_data,
                idempotency_key=idempotency_key,
            )
            # Commit before dispatch so the worker (a separate session) can find the row.
            await self.run_repository.db.commit()
        except IntegrityError:
            # Two concurrent deliveries with the same key: the loser returns the winner.
            await self.run_repository.db.rollback()
            existing = (
                await self.run_repository.get_by_idempotency_key(webhook.id, idempotency_key)
                if idempotency_key
                else None
            )
            if existing:
                return self._delivery_response(existing, duplicate=True), 200
            raise

        tenant_id = get_tenant_context() or "master"
        await self._dispatch(run.id, tenant_id, request)
        return self._delivery_response(run, duplicate=False), 202

    @staticmethod
    def _delivery_response(run, duplicate: bool) -> WorkflowTriggerDeliveryResponse:
        return WorkflowTriggerDeliveryResponse(
            run_id=run.id, status=run.status, thread_id=run.thread_id, duplicate=duplicate
        )

    async def _dispatch(self, run_id: UUID, tenant_id: str, request: Optional[Request]) -> None:
        celery_app = getattr(getattr(request, "app", None), "celery_app", None)
        try:
            if celery_app is not None:
                result = celery_app.send_task(TRIGGER_TASK_NAME, args=[str(run_id), tenant_id])
                logger.info("Queued webhook trigger run %s (task %s)", run_id, result.id)
                return
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("send_task failed for webhook trigger run %s: %s", run_id, exc, exc_info=True)
        try:
            from app.tasks.workflow_trigger_tasks import execute_webhook_trigger_run_task

            execute_webhook_trigger_run_task.delay(str(run_id), tenant_id)
            logger.info("Queued webhook trigger run %s (fallback)", run_id)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Could not queue webhook trigger run %s: %s", run_id, exc, exc_info=True)
            await self.run_repository.update_status(
                run_id, WorkflowScheduleRunStatus.FAILED, error_message="Could not queue the run"
            )
            await self.run_repository.db.commit()
            raise HTTPException(status_code=503, detail="Could not queue the run; retry later")
