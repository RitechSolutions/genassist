# Webhook Trigger Node

The **Webhook Trigger** node lets an external system start a GenAssist workflow through an
inbound HTTP request. Each node gets its own authenticated endpoint; a valid delivery is
queued as a workflow run and answered immediately with `202 Accepted` and a run id.

## Why it matters

Until now a workflow could only begin from a chat message or a schedule. The Webhook Trigger
adds externally triggered automation: a new order, a CRM change, a monitoring alert, a form
submission or any system without a dedicated connector can start a workflow with a plain
HTTP call.

## How to enable

The node is hidden behind the feature flag `workflow.webhookTrigger` (seeded `false` by
migration `00113`). Set it to `true` in **Settings → Feature Flags** to show the node in the
builder's palette, canvas context menu and ⌘K results. Nodes already on a canvas keep
working regardless of the flag.

## How to use

1. Drag **Webhook Trigger** (I/O category) onto the canvas and wire its **output** into the
   rest of the flow. A workflow may contain both a **Start** (Chat Input) node and a Webhook
   Trigger; each run starts from exactly one of them and the other is skipped.
2. Open the node settings. The **Endpoint** tab generates the endpoint URL and shows the
   secret **once** — copy it. Choose the HTTP method (`POST`/`GET`), the authentication mode
   and a per-minute rate limit, then **Apply endpoint settings**. These live on the endpoint,
   not the workflow version, so publishing never rotates a secret.
3. **Save the workflow.** The endpoint answers `404` until the node is part of the agent's
   published workflow.
4. On the **Mapping** tab, optionally set:
   - **Message path** – the value that becomes the workflow `message` (also writes the run
     to conversation memory). Leave empty for event-style payloads.
   - **Thread id path** – groups deliveries into one conversation thread.
   - **Idempotency key path** – a redelivery with the same key returns the first run. An
     `Idempotency-Key` header is always honoured.
   - **Extra input fields** – expose parts of the payload as top-level inputs.
   Paths are dotted and start at the delivery envelope: `body.order.id`, `headers.x-event-type`,
   `query.source`.
5. Paste a **sample payload**, check the input preview, and **Send test delivery** to queue a
   real run without authentication. Runs appear on the **Runs** tab with status, input and
   redacted output.

## Calling the endpoint

```
POST {api}/webhook/execute/{id}?x-tenant-id={tenant}
Authorization: Bearer <secret>
Content-Type: application/json

{"event": "order.created", "order": {"id": "ord_123"}}
```

Responses:

| Status | Meaning |
| --- | --- |
| `202` | Queued. Body: `{ "run_id", "status": "pending", "thread_id", "duplicate": false }` |
| `200` | Duplicate delivery (same idempotency key); body carries the original run |
| `401` | Missing/invalid token or signature, or stale timestamp |
| `404` | Unknown, disabled or deleted endpoint; node not in the published workflow |
| `405` | Wrong HTTP method |
| `409` | Agent inactive, no published workflow, or node deactivated |
| `413` | Body larger than 1 MiB |
| `422` | Payload does not satisfy the field mapping (`errors` lists why) |
| `429` | Per-endpoint rate limit exceeded |

**HMAC mode**: send `X-GenAssist-Timestamp: <unix seconds>` and
`X-GenAssist-Signature: sha256=<hex>` where the signature is
`HMAC_SHA256(secret, "{timestamp}.{raw body}")`. Timestamps older than 5 minutes are rejected.
Both modes use constant-time comparison and fail closed when the stored secret cannot be
decrypted.

## What downstream nodes receive

The trigger node's output (and the engine's initial input) is:

```json
{
  "webhook": {
    "method": "POST",
    "headers": { "content-type": "application/json", "x-event-type": "order.created" },
    "query": {},
    "body": { "...": "the parsed JSON body, or { \"raw\": \"...\" } for non-JSON" },
    "received_at": "2026-09-24T10:00:00+00:00",
    "is_test": false
  },
  "message": "only when a message path is configured",
  "order_id": "any extra mapped fields"
}
```

`authorization`, `cookie` and signature headers are stripped before the delivery is stored.
When the node runs without a delivery (builder Test button or a schedule) it falls back to its
sample payload with `is_test: true`.

## Architecture

- **Endpoint row**: `webhooks` with `webhook_type = 'workflow_trigger'`, bound by
  `agent_id + node_id` (new columns `node_id`, `auth_mode`, `rate_limit_per_minute`). Secrets
  are Fernet-encrypted like other webhooks. The public route `/webhook/execute/{id}` is
  reused; the service dispatches on the webhook type.
- **Run history**: `workflow_trigger_runs` mirrors `workflow_schedule_runs`
  (`PENDING → RUNNING → COMPLETED/FAILED`, PII-redacted `execution_output`), plus
  `idempotency_key` with a partial unique index. The stuck-run reconciler covers it.
- **Execution**: Celery task `execute_webhook_trigger_run` on the `ml` queue, scoped to the
  tenant known at enqueue time. It resolves the agent's *current* workflow (like schedules)
  and starts the engine at the trigger node.
- **Engine**: `entry_nodes.py` declares the entry node types. A run that starts at an entry
  node ignores the workflow's other entry nodes in requirement checks and input merging, so a
  node fed by both Start and the trigger never hangs.
- **Management API**: `genagent/workflow-triggers/*` — provision, by-agent, get, update,
  delete, rotate-secret, reveal-secret, runs, runs/{id}, test.

## Known limits

- Deleting the node from the canvas does not delete its endpoint; the endpoint answers `404`
  because the node is no longer in the published workflow. Use **Delete** in the management
  API (or re-add a node with the same id) to clean up.
- Deliveries are asynchronous; there is no synchronous "wait for the result" mode yet.
- `input_data` is stored as received (minus credentials) so the worker can run it; the run
  output is PII-redacted before it is persisted.
