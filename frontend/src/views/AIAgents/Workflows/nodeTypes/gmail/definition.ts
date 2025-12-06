import { NodeTypeDefinition } from "../../types/nodes";
import GmailNode from "../gmail/gmailNode";
import { GmailNodeData } from "../../types/nodes";
import { NodeProps } from "reactflow";

export const GMAIL_NODE_DEFINITION: NodeTypeDefinition<GmailNodeData> = {
  type: "gmailNode",
  label: "Gmail Output",
  description: "Send an email via Gmail API",
  category: "tools",
  icon: "Mail",
  defaultData: {
    name: "Gmail Output",
    subject: "",
    body: "",
    to: "",
    cc: "",
    bcc: "",
    attachments: [],
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "text",
      },
    ],
  },
  component: GmailNode as React.ComponentType<NodeProps<GmailNodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "gmailNode",
    position,
    data: {
      ...data,
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "text",
        },
        {
          id: "output",
          type: "source",
          compatibility: "text",
        },
        ...data.handlers,
      ],
    },
  }),
};