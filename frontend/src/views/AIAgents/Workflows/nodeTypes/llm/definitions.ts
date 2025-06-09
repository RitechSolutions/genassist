import { NodeProps } from "reactflow";
import { NodeData, NodeTypeDefinition, AgentNodeData, LLMModelNodeData } from "../../types/nodes";
import AgentNode from "./agentNode";
import LLMModelNode from "./modelNode";

export const AGENT_NODE_DEFINITION: NodeTypeDefinition<AgentNodeData> = {
  type: "agentNode",
  label: "Agent",
  description: "An agent that can use tools to process inputs",
  category: "process",
  icon: "Brain",
  defaultData: {
    name:"Agent",
    providerId: "openai",
    outputFormat: "string",
    handlers: [],
  },
  component: AgentNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "agentNode",
    position,
    data: {
      ...data,
      handlers: [
        {
          id: "input_prompt",
          type: "target",
          compatibility: "text",
        },
        {
          id: "input_tools",
          type: "target",
          compatibility: "tools",
        },
        {
          id: "output",
          type: "source",
          compatibility: "text",
        },
      ],
    },
  }),
};

export const MODEL_NODE_DEFINITION: NodeTypeDefinition<LLMModelNodeData> = {
    type: "llmModelNode",
    label: "LLM Model",
    description: "Configure an LLM model provider and settings",
    category: "process",
    icon: "Brain",
    defaultData: {
      name: "LLM Model",
      providerId: "openai",
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
      ],
    },
    component: LLMModelNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "llmModelNode",
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
        ],
      },
    }),
  }