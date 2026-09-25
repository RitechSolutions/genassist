/**
 * Entry (trigger) node types: the nodes a workflow run can start from.
 *
 * Mirrors `backend/app/modules/workflow/engine/entry_nodes.py`. A workflow may
 * carry more than one (Chat Input for the chat channel, Webhook Trigger for
 * external systems); a run starts from exactly one of them.
 */
export const CHAT_INPUT_NODE_TYPE = "chatInputNode";
export const WEBHOOK_TRIGGER_NODE_TYPE = "webhookTriggerNode";

export const ENTRY_NODE_TYPES: ReadonlySet<string> = new Set([
  CHAT_INPUT_NODE_TYPE,
  WEBHOOK_TRIGGER_NODE_TYPE,
]);

export const isEntryNodeType = (type?: string | null): boolean =>
  !!type && ENTRY_NODE_TYPES.has(type);
