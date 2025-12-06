import { NodeProps } from "reactflow";
import {
  NodeData,
  NodeTypeDefinition,
  AgentNodeData,
  LLMModelNodeData,
  ToolBuilderNodeData,
} from "../../types/nodes";
import AgentNode from "./agentNode";
import LLMModelNode from "./modelNode";
import ToolBuilderNode from "./toolBuilderNode";

export const AGENT_NODE_DEFINITION: NodeTypeDefinition<AgentNodeData> = {
  type: "agentNode",
  label: "AI Agent",
  description:
    "Runs an AI-powered agent capable of reasoning, taking actions, and calling tools.",
  shortDescription: "Run an AI agent",
  configSubtitle:
    "Configure the AI agent settings, including provider, agent type, prompts, and memory.",
  category: "ai",
  icon: "Bot",
  defaultData: {
    name: "AI Agent",
    providerId: undefined,
    type: "ToolSelector",
    memory: false,
    systemPrompt: "",
    userPrompt: "{{source.message}}",
    maxIterations: 7,
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "input_tools",
        type: "target",
        compatibility: "tools",
        position: "bottom",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
      },
    ],
  },
  component: AgentNode as React.ComponentType<NodeProps<NodeData>>,
  createNode: (id, position, data) => ({
    id,
    type: "agentNode",
    position,
    data: {
      ...data,
    },
  }),
};

export const MODEL_NODE_DEFINITION: NodeTypeDefinition<LLMModelNodeData> = {
  type: "llmModelNode",
  label: "Language Model",
  description:
    "Runs a large language model using a prompt and adjustable model settings.",
  shortDescription: "Run a language model",
  configSubtitle:
    "Configure the language model settings, including provider, prompts, and memory options.",
  category: "ai",
  icon: "Brain",
  defaultData: {
    name: "Language Model",
    providerId: undefined,
    memory: false,
    type: "Base",
    systemPrompt: "",
    userPrompt: "{{source.message}}",
    handlers: [
      {
        id: "input",
        type: "target",
        compatibility: "any",
        position: "left",
      },
      {
        id: "output",
        type: "source",
        compatibility: "any",
        position: "right",
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
    },
  }),
};
export const TOOL_BUILDER_NODE_DEFINITION: NodeTypeDefinition<ToolBuilderNodeData> =
  {
    type: "toolBuilderNode",
    label: "Tool Builder",
    description:
      "Defines a custom tool that an AI agent can call, including parameters and output templates.",
    shortDescription: "Define a custom tool",
    configSubtitle:
      "Configure the custom tool definition, including description, parameters, and output template.",
    category: "ai",
    icon: "Wrench",
    defaultData: {
      name: "Tool Builder",
      description: "Custom tool for parameter forwarding",
      inputSchema: undefined,
      forwardTemplate: "{{direct_input}}",
      handlers: [
        {
          id: "output_tool",
          type: "source",
          compatibility: "tools",
          position: "top",
        },
        {
          id: "starter_processor",
          type: "source",
          compatibility: "any",
          position: "right",
        },
        // {
        //   id: "end_processor",
        //   type: "target",
        //   compatibility: "any",
        //   position: "bottom",
        // },
      ],
    },
    component: ToolBuilderNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "toolBuilderNode",
      position,
      data: {
        ...data,
      },
    }),
  };
