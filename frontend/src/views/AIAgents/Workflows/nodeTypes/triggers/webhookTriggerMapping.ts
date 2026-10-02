/**
 * Client-side preview of the Webhook Trigger payload mapping.
 *
 * A TypeScript port of `backend/app/modules/workflow/webhook_trigger_mapping.py`
 * so the dialog can show what a delivery becomes before anything is sent. The
 * backend is the source of truth; keep the two in sync.
 */

import type { WebhookFieldMapping, WebhookTriggerNodeData } from "../../types/nodes";

export type JsonLike = unknown;

export interface WebhookEnvelope {
  method: string;
  headers: Record<string, unknown>;
  query: Record<string, unknown>;
  body: JsonLike;
  received_at: string;
  is_test: boolean;
}

export const RESERVED_INPUT_KEYS: ReadonlySet<string> = new Set([
  "webhook",
  "thread_id",
  "status",
  "output",
  "workflow",
  "workflow_id",
  "memory",
  "session",
  "initial_values",
  "errors",
  "execution_id",
  "node_outputs",
  "is_executing",
]);

const KEY_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

/** Resolve a dotted path over objects and arrays. Object keys match exactly first, then case-insensitively. */
export const getPath = (data: JsonLike, path: string): { found: boolean; value: unknown } => {
  if (!path) return { found: false, value: undefined };
  let current: unknown = data;
  for (const segment of path.split(".")) {
    if (Array.isArray(current)) {
      const index = Number(segment);
      if (!Number.isInteger(index) || index < 0 || index >= current.length) {
        return { found: false, value: undefined };
      }
      current = current[index];
    } else if (current && typeof current === "object") {
      const record = current as Record<string, unknown>;
      if (segment in record) {
        current = record[segment];
        continue;
      }
      const lowered = segment.toLowerCase();
      const match = Object.keys(record).find((k) => k.toLowerCase() === lowered);
      if (match === undefined) return { found: false, value: undefined };
      current = record[match];
    } else {
      return { found: false, value: undefined };
    }
  }
  return { found: true, value: current };
};

export const buildEnvelope = (body: JsonLike, options?: Partial<WebhookEnvelope>): WebhookEnvelope => ({
  method: (options?.method ?? "POST").toUpperCase(),
  headers: Object.fromEntries(
    Object.entries(options?.headers ?? {}).map(([k, v]) => [k.toLowerCase(), v])
  ),
  query: { ...(options?.query ?? {}) },
  body,
  received_at: options?.received_at ?? new Date().toISOString(),
  is_test: options?.is_test ?? true,
});

/** The node's sample payload as data; invalid JSON becomes `{ raw }` like the backend. */
export const parseSamplePayload = (text: string | undefined | null): JsonLike => {
  const trimmed = (text ?? "").trim();
  if (!trimmed) return {};
  try {
    return JSON.parse(trimmed);
  } catch {
    return { raw: text };
  }
};

export interface MappingPreview {
  input: Record<string, unknown>;
  errors: string[];
}

/** Map an envelope onto the engine input the way the backend does. */
export const buildTriggerInput = (
  envelope: WebhookEnvelope,
  nodeData: Pick<WebhookTriggerNodeData, "fieldMappings" | "messagePath" | "messageRequired">
): MappingPreview => {
  const errors: string[] = [];
  const input: Record<string, unknown> = { webhook: envelope };

  (nodeData.fieldMappings ?? []).forEach((mapping: WebhookFieldMapping, index) => {
    const key = (mapping.key ?? "").trim();
    const path = (mapping.path ?? "").trim();
    if (!key && !path) return;
    if (!KEY_RE.test(key)) {
      errors.push(`Mapping #${index + 1}: '${key}' is not a valid input key`);
      return;
    }
    if (RESERVED_INPUT_KEYS.has(key)) {
      errors.push(`Mapping #${index + 1}: '${key}' is reserved`);
      return;
    }
    const { found, value } = path ? getPath(envelope, path) : { found: false, value: undefined };
    if (found) {
      input[key] = value;
      return;
    }
    const hasDefault = mapping.default !== undefined && mapping.default !== null && mapping.default !== "";
    if (hasDefault) {
      input[key] = mapping.default;
    } else if (mapping.required) {
      errors.push(`Required field '${key}' not found at '${path}'`);
    } else {
      input[key] = mapping.default;
    }
  });

  const messagePath = (nodeData.messagePath ?? "").trim();
  if (messagePath) {
    const { found, value } = getPath(envelope, messagePath);
    if (found && value !== null && value !== undefined) {
      input.message = typeof value === "string" ? value : JSON.stringify(value);
    } else if (nodeData.messageRequired) {
      errors.push(`Message not found at '${messagePath}'`);
    } else {
      input.message = "";
    }
  }

  return { input, errors };
};

/** Sample engine input for the builder's variable pickers / execution preview. */
export const sampleTriggerOutput = (nodeData: WebhookTriggerNodeData): Record<string, unknown> => {
  const envelope = buildEnvelope(parseSamplePayload(nodeData.samplePayload), { is_test: true });
  return buildTriggerInput(envelope, nodeData).input;
};

/** A ready-to-paste curl command for the endpoint. */
export const buildCurlExample = (
  url: string,
  method: "POST" | "GET",
  authMode: "bearer" | "hmac",
  sampleBody: string
): string => {
  const body = sampleBody.trim() || "{}";
  const compact = (() => {
    try {
      return JSON.stringify(JSON.parse(body));
    } catch {
      return body;
    }
  })();
  if (authMode === "hmac") {
    return [
      `SECRET='<your secret>'`,
      `BODY='${compact.replace(/'/g, "'\\''")}'`,
      `TS=$(date +%s)`,
      `SIG=sha256=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* //')`,
      `curl -X ${method} '${url}' \\`,
      `  -H 'Content-Type: application/json' \\`,
      `  -H "X-GenAssist-Timestamp: $TS" \\`,
      `  -H "X-GenAssist-Signature: $SIG" \\`,
      ...(method === "GET" ? [] : [`  --data "$BODY"`]),
    ]
      .join("\n")
      .replace(/ \\\n$/, "");
  }
  const lines = [
    `curl -X ${method} '${url}' \\`,
    `  -H 'Authorization: Bearer <your secret>' \\`,
    `  -H 'Content-Type: application/json'`,
  ];
  if (method !== "GET") {
    lines[lines.length - 1] += " \\";
    lines.push(`  --data '${compact.replace(/'/g, "'\\''")}'`);
  }
  return lines.join("\n");
};
