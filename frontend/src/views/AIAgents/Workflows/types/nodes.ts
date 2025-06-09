import { Edge, Node, NodeProps } from "reactflow";
import { ComponentType } from "react";
import { NodeSchema } from "./schemas";

// Define compatibility types
export type NodeCompatibility = "text" | "tools" | "llm" | "json" | "any";

// Define handler types
export interface NodeHandler {
  id: string;
  type: "source" | "target";
  compatibility: NodeCompatibility;
  schema?: NodeSchema;
}

// Base node data interface
export interface BaseNodeData {
  name: string;
  handlers: NodeHandler[];
  updateNodeData?: <T extends BaseNodeData>(
    nodeId: string,
    data: Partial<T>
  ) => void;
}

export interface ToolBaseNodeData extends BaseNodeData {
  description: string;
  inputSchema?: NodeSchema;
  outputSchema?: NodeSchema;
}

// Chat input node data
export type ChatInputNodeData = BaseNodeData;
// LLM Model node data
export interface LLMModelNodeData extends BaseNodeData {
  providerId: string;
  jsonParsing?: boolean;
}

// Prompt Template node data
export interface TemplateNodeData extends BaseNodeData {
  template: string;
  includeHistory?: boolean;
}

// Chat Output node data
export type ChatOutputNodeData = BaseNodeData;

// Slack Output node data
export interface SlackOutputNodeData extends BaseNodeData{
  token: string; // authentication token
  channel: string; // target Slack channel or user ID/email
  message: string; // the most recent message to send to Slack
}


export interface ZendeskTicketNodeData extends BaseNodeData {
  subject: string;
  description: string;
  requester_name?: string;
  requester_email?: string;
  tags?: string[];
  custom_fields?: Array<{ id: number; value: string | number }>;
}

// API Tool Node Data
export interface APIToolNodeData extends ToolBaseNodeData {
  endpoint: string;
  method: string;
  headers: Record<string, string>;
  parameters: Record<string, string>;
  requestBody: string;
}

// Agent Node Data
export interface AgentNodeData extends BaseNodeData {
  providerId: string;
  outputFormat?: "json" | "string";
  jsonParsing?: boolean;
  // onPromptReceived?: (text: string) => void;
  // onToolsReceived?: (
  //   tools: Array<{
  //     id: string;
  //     name: string;
  //     description: string;
  //     category: string;
  //   }>
  // ) => void;
}

// Knowledge Base Node Data
export interface KnowledgeBaseNodeData extends ToolBaseNodeData {
  selectedBases: string[];
}

// Python Code Node Data
export interface PythonCodeNodeData extends ToolBaseNodeData {
  code: string;
}



// Union type for all node data types
export type NodeData =
  | ChatInputNodeData
  | LLMModelNodeData
  | TemplateNodeData
  | ChatOutputNodeData
  | APIToolNodeData
  | AgentNodeData
  | KnowledgeBaseNodeData
  | PythonCodeNodeData
  | SlackOutputNodeData;


// Node type definition
export interface NodeTypeDefinition<T extends NodeData> {
  type: string;
  label: string;
  description: string;
  category: "input" | "process" | "output" | "config" | "tools";
  icon: string;
  defaultData: T;
  component: ComponentType<NodeProps<NodeData>>; // React component for the node
  createNode: (
    id: string,
    position: { x: number; y: number },
    data: T
  ) => Node;
}

// Function to create a node with the given data
export const createNode = <T extends NodeData>(
  type: string,
  id: string,
  position: { x: number; y: number },
  data: T
): Node => {
  return {
    id,
    type,
    position,
    data: data,
  };
};

export const createEdge = (
  source: string,
  target: string,
  data: Record<string, unknown>
): Edge => {
  return {
    id: `${source}-${target}`,
    sourceHandle: source,
    targetHandle: target,
    source,
    target,
    data,
  };
};

