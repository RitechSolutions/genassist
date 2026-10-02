from typing import List

from ..base import FieldSchema

# The `fieldMappings` list ([{key, path, required, default}]) and the endpoint
# settings (method, auth mode, secret, rate limit) are edited in the node's own
# dialog. The endpoint settings live on the trigger's `webhooks` row, not in the
# node data, so publishing a new workflow version never rotates a secret.
WEBHOOK_TRIGGER_NODE_DIALOG_SCHEMA: List[FieldSchema] = [
    FieldSchema(
        name="name",
        type="text",
        label="Node Name",
        required=False,
    ),
    FieldSchema(
        name="messagePath",
        type="text",
        label="Message path",
        required=False,
        placeholder="body.message",
        description=(
            "Path in the delivery whose value becomes the workflow `message`. "
            "Leave empty for event-style payloads that carry no user message."
        ),
    ),
    FieldSchema(
        name="threadIdPath",
        type="text",
        label="Thread id path",
        required=False,
        placeholder="body.conversation_id",
        description="Path whose value groups deliveries into one conversation thread. Empty = a new thread per run.",
    ),
    FieldSchema(
        name="idempotencyPath",
        type="text",
        label="Idempotency key path",
        required=False,
        placeholder="body.event_id",
        description="Path to a unique delivery id. An `Idempotency-Key` header is always honoured too.",
    ),
    FieldSchema(
        name="samplePayload",
        type="textarea",
        label="Sample payload (JSON)",
        required=False,
        size="code",
        description="Used by the Test button and to preview mappings. Never sent anywhere.",
    ),
]
