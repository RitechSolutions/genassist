import {
  ChatInputNodeData,
  ChatOutputNodeData,
  NodeData,
  NodeTypeDefinition,
} from "../../types/nodes";
import ChatInputNode from "./chatInputNode";

import { NodeProps } from "reactflow";
import ChatOutputNode from "./chatOutputNode";
import { createSimpleSchema } from "../../types/schemas";

export const CHAT_INPUT_NODE_DEFINITION: NodeTypeDefinition<ChatInputNodeData> =
  {
    type: "chatInputNode",
    label: "Start",
    description:
      "Defines the entry point of the workflow where inputs are received.",
    shortDescription: "Start workflow execution",
    category: "io",
    icon: "ArrowRightFromLine",
    defaultData: {
      name: "Start",
      inputSchema: createSimpleSchema({
        message: {
          type: "string",
          description: "The message received from the user",
          required: true,
        },
      }),
      handlers: [
        {
          id: "output",
          type: "source",
          compatibility: "any",
          position: "right",
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
      },
    }),
  };

export const CHAT_OUTPUT_NODE_DEFINITION: NodeTypeDefinition<ChatOutputNodeData> =
  {
    type: "chatOutputNode",
    label: "Finish",
    description:
      "Defines the endpoint of the workflow where final outputs are delivered.",
    shortDescription: "Finish workflow execution",
    category: "io",
    icon: "ArrowRightToLine",
    defaultData: {
      name: "Finish",
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "any",
          position: "left",
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
      },
    }),
  };
