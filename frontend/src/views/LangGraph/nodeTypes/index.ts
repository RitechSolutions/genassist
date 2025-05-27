import React from "react";
import { NodeProps } from "reactflow";
import nodeRegistry from "../registry/nodeRegistry";
import { NodeData, NodeTypeDefinition } from "../types/nodes";
import ChatInputNode from "./chatInputNode";
import LLMModelNode from "./llmModelNode";
import PromptNode from "./promptNode";
import ChatOutputNode from "./chatOutputNode";
import APIToolNode from "./apiToolNode";
import AgentNode from "./agentNode";
import KnowledgeBaseNode from "./knowledgeBaseNode";
import MapperNode from "./mapperNode";

// Define node types
// Config node has been removed

const chatInputNodeType: NodeTypeDefinition = {
  type: "chatInputNode",
  label: "Chat Input",
  description: "A node for handling chat messages and user inputs",
  category: "input",
  icon: "MessageCircle",
  component: ChatInputNode,
  defaultData: {
    label: "Chat Input",
    placeholder: "Type a message...",
    onMessageSubmit: (message: string) => {
      console.log("Message submitted:", message);
    },
  },
  createNode: (id, position, data) => ({
    id,
    type: "chatInputNode",
    position,
    data: {
      label: (data.label as string) || "Chat Input",
      placeholder: data.placeholder as string,
      onMessageSubmit:
        (data.onMessageSubmit as (message: string) => void) ||
        ((message: string) => {
          console.log("Message submitted:", message);
        }),
    },
  }),
};

// Register node types right away
if (nodeRegistry.getAllNodeTypes().length === 0) {
  // Config node registration removed
  nodeRegistry.register(chatInputNodeType);
  console.log(
    "Node types registered at module level:",
    nodeRegistry.getAllNodeTypes().length
  );
}

// A function to re-register if needed
export const registerAllNodeTypes = () => {
  // Clear existing registry to prevent duplicates
  nodeRegistry.clearRegistry();

  // Register ChatInput node
  nodeRegistry.registerNodeType({
    type: "chatInputNode",
    label: "Chat Input",
    description: "A node for handling chat messages and user inputs",
    category: "input",
    icon: "MessageCircle",
    defaultData: {
      label: "Chat Input",
      placeholder: "Type a message...",
      handlers: [
        {
          id: "output",
          type: "source",
          compatibility: "text",
        },
      ],
      onMessageSubmit: (message: string) => {
        console.log("Message submitted:", message);
      },
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
        ],
      },
    }),
  });

  // Register LLM Model node
  nodeRegistry.registerNodeType({
    type: "llmModelNode",
    label: "LLM Model",
    description: "Configure an LLM model provider and settings",
    category: "process",
    icon: "Brain",
    defaultData: {
      label: "LLM Model",
      providerId: "openai",
      localConfig: {
        provider: "openai",
        model: "gpt-3.5-turbo",
        apiKey: "",
        temperature: 0.7,
        maxTokens: 1024,
      },
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
  });

  // Register Prompt Template node
  nodeRegistry.registerNodeType({
    type: "promptNode",
    label: "Prompt Template",
    description: "Create dynamic prompt templates with placeholders",
    category: "process",
    icon: "FileText",
    defaultData: {
      label: "Prompt Template",
      template:
        "You are my assistent! Please answer the following question: {{user_query}}",
      handlers: [
        {
          id: "output",
          type: "source",
          compatibility: "text",
        },
      ],
    },
    component: PromptNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "promptNode",
      position,
      data: {
        ...data,
        handlers: [
          {
            id: "output",
            type: "source",
            compatibility: "text",
          },
        ],
      },
    }),
  });

  // Register Chat Output node
  nodeRegistry.registerNodeType({
    type: "chatOutputNode",
    label: "Chat Output",
    description: "Display chat messages from the LLM",
    category: "output",
    icon: "MessageSquare",
    defaultData: {
      label: "Chat Output",
      messages: [],
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
        ],
      },
    }),
  });

  // Register API Tool node
  nodeRegistry.registerNodeType({
    type: "apiToolNode",
    label: "API Tool",
    description: "Make real-time API calls to external services",
    category: "tools",
    icon: "Globe",
    defaultData: {
      name: "API Tool",
      description: "Makes API calls to external services",
      endpoint: "https://",
      method: "GET",
      headers: {},
      parameters: {},
      requestBody: "",
      response: "",
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "json",
        },

        {
          id: "output_reference",
          type: "source",
          compatibility: "tools",
        },
        {
          id: "output",
          type: "source",
          compatibility: "json",
        },
      ],
    },
    component: APIToolNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "apiToolNode",
      position,
      data: {
        ...data,
        handlers: [
          {
            id: "input",
            type: "target",
            compatibility: "json",
          },
  
          {
            id: "output_reference",
            type: "source",
            compatibility: "tools",
          },
          {
            id: "output",
            type: "source",
            compatibility: "json",
          },
        ],
      },
    }),
  });

  // Register Knowledge Base node
  nodeRegistry.registerNodeType({
    type: "knowledgeBaseNode",
    label: "Knowledge Base",
    description: "Query multiple knowledge bases for information",
    category: "tools",
    icon: "Database",
    defaultData: {
      name: "Knowledge Base",
      description: "Query multiple knowledge bases",
      selectedBases: [],
      query: "",
      output: "",
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "json",
        },

        {
          id: "output_reference",
          type: "source",
          compatibility: "tools",
        },
        {
          id: "output",
          type: "source",
          compatibility: "json",
        },
      ],
    },
    component: KnowledgeBaseNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "knowledgeBaseNode",
      position,
      data: {
        ...data,
        handlers: [
          {
            id: "input",
            type: "target",
            compatibility: "json",
          },
  
          {
            id: "output_reference",
            type: "source",
            compatibility: "tools",
          },
          {
            id: "output",
            type: "source",
            compatibility: "json",
          },
        ],
      },
    }),
  });

  // Register Agent node
  nodeRegistry.registerNodeType({
    type: "agentNode",
    label: "Agent",
    description: "An agent that can use tools to process inputs",
    category: "process",
    icon: "Brain",
    defaultData: {
      label: "Agent",
      providerId: "openai",
      localConfig: {
        provider: "openai",
        model: "gpt-3.5-turbo",
        apiKey: "",
        temperature: 0.7,
        maxTokens: 1024,
      },
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
  });

  // Register Mapper node
  nodeRegistry.registerNodeType({
    type: "mapperNode",
    label: "Field Mapper",
    description: "Map input fields to output fields",
    category: "process",
    icon: "ArrowRightLeft",
    defaultData: {
      label: "Field Mapper",
      mappings: [{ inputField: "", outputField: "" }],
      handlers: [
        {
          id: "input",
          type: "target",
          compatibility: "json",
        },
        {
          id: "output",
          type: "source",
          compatibility: "json",
        },
      ],
    },
    component: MapperNode as React.ComponentType<NodeProps<NodeData>>,
    createNode: (id, position, data) => ({
      id,
      type: "mapperNode",
      position,
      data: {
        ...data,
        handlers: [
          {
            id: "input",
            type: "target",
            compatibility: "json",
          },
          {
            id: "output",
            type: "source",
            compatibility: "json",
          },
        ],
      },
    }),
  });
};

// Get node types for React Flow
export const getNodeTypes = () => {
  return {
    chatInputNode: ChatInputNode,
    llmModelNode: LLMModelNode,
    promptNode: PromptNode,
    chatOutputNode: ChatOutputNode,
    apiToolNode: APIToolNode,
    agentNode: AgentNode,
    knowledgeBaseNode: KnowledgeBaseNode,
    mapperNode: MapperNode,
  };
};
