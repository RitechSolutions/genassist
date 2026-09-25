import type { NodeHelpContent } from "../../types/nodes";

export const WEBHOOK_TRIGGER_NODE_HELP_CONTENT: NodeHelpContent = {
  intro:
    "The Webhook Trigger starts a workflow from an inbound HTTP request. Each node gets its own authenticated endpoint; an external system calls it and the workflow runs in the background with the delivery as its input.",
  sections: [
    {
      title: "Overview & Use Cases",
      body: "Use the Webhook Trigger when a workflow should start from an event in another system instead of a chat message:",
      bullets: [
        "A new order, support request, form submission or system alert",
        "A CRM or SaaS platform reporting that a customer, account or ticket changed",
        "Monitoring or internal tooling firing on an incident or threshold",
        "A customer-facing application kicking off automation without a chat",
        "Any system without a dedicated connector, through a plain HTTP call",
      ],
    },
    {
      title: "How it works",
      bullets: [
        "Open the node settings to generate its endpoint URL and secret. Save the workflow so the node is part of the published version.",
        "The caller authenticates with a bearer token, or signs the body with HMAC-SHA256 (X-GenAssist-Timestamp / X-GenAssist-Signature).",
        "A valid delivery is queued and answered with 202 and a run id; the run appears under Recent runs.",
        "Downstream nodes receive the delivery as `webhook` ({ method, headers, query, body }) plus any fields you map.",
        "Map a path to `message` when the payload carries a user message; that also writes the run to conversation memory.",
        "Retried deliveries are ignored when they carry the same Idempotency-Key header (or the configured idempotency path).",
      ],
    },
    {
      title: "Chat Input and Webhook Trigger together",
      body: "A workflow may have both. A chat message starts at Chat Input and a delivery starts at the Webhook Trigger; the other entry node is skipped for that run, so downstream nodes never wait on it.",
    },
  ],
};
