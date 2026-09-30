import { NodeProps } from "reactflow";
import { NodeData, NodeTypeDefinition, WebhookTriggerNodeData } from "../../types/nodes";
import WebhookTriggerNode from "./webhookTriggerNode";
import { WEBHOOK_TRIGGER_NODE_HELP_CONTENT } from "./helperDefinition";
import { WEBHOOK_TRIGGER_NODE_TYPE } from "../../utils/entryNodes";

export const DEFAULT_WEBHOOK_SAMPLE_PAYLOAD = JSON.stringify(
  {
    event: "order.created",
    order: { id: "ord_123", total: 49.9, customer_email: "jane@example.com" },
    message: "New order ord_123 placed",
  },
  null,
  2
);

export const WEBHOOK_TRIGGER_NODE_DEFINITION: NodeTypeDefinition<WebhookTriggerNodeData> = {
  type: WEBHOOK_TRIGGER_NODE_TYPE,
  label: "Webhook Trigger",
  description:
    "Starts the workflow from an inbound HTTP request. Each node gets its own authenticated endpoint; the delivery becomes the workflow input.",
  shortDescription: "Start from an HTTP request",
  helpContent: WEBHOOK_TRIGGER_NODE_HELP_CONTENT,
  configSubtitle:
    "Generate the endpoint, choose how callers authenticate, and map the payload to workflow inputs.",
  category: "io",
  icon: "Webhook",
  defaultData: {
    name: "Webhook Trigger",
    fieldMappings: [],
    messagePath: "",
    threadIdPath: "",
    idempotencyPath: "",
    samplePayload: DEFAULT_WEBHOOK_SAMPLE_PAYLOAD,
    handlers: [
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: WebhookTriggerNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: WEBHOOK_TRIGGER_NODE_TYPE,
    position,
    data: {
      ...data,
    },
  }),
};
