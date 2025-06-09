import { NodeTypeDefinition } from "../../types/nodes";
import ZendeskTicketNode from "../zendesk/zendeskTicketNode";
import { ZendeskTicketNodeData } from "../../types/nodes";
import { NodeProps } from "reactflow";

export const ZENDESK_TICKET_NODE_DEFINITION: NodeTypeDefinition<ZendeskTicketNodeData> = {
  type: "zendeskTicketNode",
  label: "Zendesk Ticket",
  description: "Create a new Zendesk ticket via API",
  category: "tools",
  icon: "Tag",
  defaultData: {
    name: "Zendesk Ticket",
    subject: "",
    description: "",
    requester_name: "",
    requester_email: "",
    tags: [],
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "text",
      },
    ],
  },
  component: ZendeskTicketNode as React.ComponentType<NodeProps<ZendeskTicketNodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "zendeskTicketNode",
    position,
    data: {
      ...data,
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "text",
        },
        ...data.handlers,
      ],
    },
  }),
};
