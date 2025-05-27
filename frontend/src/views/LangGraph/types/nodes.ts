import { Node, NodeProps } from 'reactflow';
import { ComponentType } from 'react';
import { NodeSchema } from './schemas';
import { LocalModelConfig } from '../components/ModelConfiguration';

// Define compatibility types
export type NodeCompatibility = 'text' | 'tools' | 'llm' | 'json' | 'any';

// Define handler types
export interface NodeHandler {
  id: string;
  type: 'source' | 'target';
  compatibility: NodeCompatibility;
  schema?: NodeSchema;
}

// Base node data interface
export interface BaseNodeData {
  label: string;
  handlers: NodeHandler[];
  updateNodeData?: <T extends BaseNodeData>(nodeId: string, data: Partial<T>) => void;
}

// Config node data
export interface ConfigNodeData extends BaseNodeData {
  properties: Record<string, string | number | boolean>;
}

// Chat input node data
export interface ChatInputNodeData extends BaseNodeData {
  placeholder?: string;
  currentMessage?: string;
  onMessageSubmit?: (message: string) => void;
  hadOnMessageSubmit?: boolean; // Used for serialization
}

// LLM Model node data
export interface LLMModelNodeData extends BaseNodeData {
  providerId: string;
  localConfig?: LocalModelConfig;
  inputText?: string;
  outputText?: string;
  jsonParsing?: boolean;
  onInputReceived?: (text: string) => void;
  onOutputChange?: (outputText: string) => void;
}

// Prompt Template node data
export interface PromptNodeData extends BaseNodeData {
  template: string;
  includeHistory?: boolean;
}

// Chat Output node data
export interface ChatOutputNodeData extends BaseNodeData {
  messages: Array<{
    id: string;
    text: string;
    timestamp: string;
    type: 'system' | 'user' | 'assistant'
  }>;
  onInputReceived?: (text: string) => void;
}

// API Tool Node Data
export interface APIToolNodeData extends BaseNodeData {
  name: string;
  description: string;
  endpoint: string;
  method: string;
  headers: Record<string, string>;
  parameters: Record<string, string>;
  requestBody: string;
  response: string;
  inputSchema?: NodeSchema;
  outputSchema?: NodeSchema;
}

// Agent Node Data
export interface AgentNodeData extends BaseNodeData {
  providerId: string;
  localConfig?: LocalModelConfig;
  inputText?: string;
  outputText?: string;
  availableTools?: Array<{
    id: string;
    name: string;
    description: string;
    category: string;
  }>;
  outputFormat?: 'json' | 'string';
  jsonParsing?: boolean;
  onPromptReceived?: (text: string) => void;
  onToolsReceived?: (tools: Array<{ id: string; name: string; description: string; category: string }>) => void;
  onOutputChange?: (outputText: string) => void;
}

// Knowledge Base Node Data
export interface KnowledgeBaseNodeData extends BaseNodeData {
  name: string;
  description: string;
  selectedBases: string[];
  query: string;
  output: string;
  inputSchema?: NodeSchema;
  outputSchema?: NodeSchema;
}

// Mapper Node Data
export interface MapperNodeData extends BaseNodeData {
  mappings: Array<{
    inputField: string;
    outputField: string;
  }>;
}

// Union type for all node data types
export type NodeData = ConfigNodeData | ChatInputNodeData | LLMModelNodeData | PromptNodeData | ChatOutputNodeData | APIToolNodeData | AgentNodeData | KnowledgeBaseNodeData | MapperNodeData;

// Node type definition
export interface NodeTypeDefinition {
  type: string;
  label: string;
  description: string;
  category: 'input' | 'process' | 'output' | 'config' | 'tools';
  icon: string;
  defaultData: Record<string, unknown>;
  component: ComponentType<NodeProps<NodeData>>; // React component for the node
  createNode: (id: string, position: { x: number; y: number }, data: Record<string, unknown>) => Node;
}

// Function to create a node with the given data
export const createNode = (
  type: string,
  id: string, 
  position: { x: number; y: number }, 
  data: Record<string, unknown>
): Node => {
  return {
    id,
    type,
    position,
    data: data
  };
}; 