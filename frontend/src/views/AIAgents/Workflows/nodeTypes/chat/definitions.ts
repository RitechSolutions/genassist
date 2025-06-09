import {
  ChatInputNodeData,
  ChatOutputNodeData,
  NodeData,
  NodeTypeDefinition,
  SlackOutputNodeData,
} from "../../types/nodes";
import ChatInputNode from "./chatInputNode";

import { NodeProps } from "reactflow";
import ChatOutputNode from "./chatOutputNode";
import SlackOutputNode from "./slackOutputNode";

export const CHAT_INPUT_NODE_DEFINITION: NodeTypeDefinition<ChatInputNodeData> =
  {
    type: "chatInputNode",
    label: "Chat Input",
    description: "A node for handling chat messages and user inputs",
    category: "input",
    icon: "MessageCircle",
    defaultData: {
      name: "Chat Input",
      handlers: [
        {
          id: "output",
          type: "source",
          compatibility: "text",
        },
      ],
    },
    component: ChatInputNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "chatInputNode",
      position,
      data: {
        ...data,
        handlers: [
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

export const CHAT_OUTPUT_NODE_DEFINITION: NodeTypeDefinition<ChatOutputNodeData> =
  {
    type: "chatOutputNode",
    label: "Chat Output",
    description: "Display chat messages from the LLM",
    category: "output",
    icon: "MessageSquare",
    defaultData: {
      name: "Chat Output",
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "text",
        },
      ],
    },
    component: ChatOutputNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "chatOutputNode",
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


  export const SLACK_OUTPUT_NODE_DEFINITION: NodeTypeDefinition<SlackOutputNodeData> =
  {
    type: "slackMessageNode",
    label: "Slack Message",
    description: "Send a message to a Slack user or channel",
    category: "output",
    icon: "Slack", 
    defaultData: {
      name: "Slack Message",
      message: "",
      channel: "",
      token: "",
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "text",
        },
      ],
    },
    component: SlackOutputNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "slackMessageNode",
      position,
      data: {
        ...data,
        handlers: [
          {
            id: "input",
            type: "target",
            compatibility: "text",
          },
        ],
      },
    }),
  }