import { Edge, Node, NodeProps } from "reactflow";
import { ComponentType } from "react";
import { NodeSchema } from "./schemas";
import { CSVAnalysisResult } from "@/services/mlModels";

// Define compatibility types
export type NodeCompatibility = "text" | "tools" | "llm" | "json" | "any";

// Define handler types
export interface NodeHandler {
  id: string;
  type: "source" | "target";
  position: "left" | "right" | "top" | "bottom";
  compatibility: NodeCompatibility;
  schema?: NodeSchema;
}

// Base node data interface
export interface BaseNodeData {
  name: string;
  handlers?: NodeHandler[];
  unwrap?: boolean;
  updateNodeData?: <T extends BaseNodeData>(
    nodeId: string,
    data: Partial<T>
  ) => void;
}

export interface ToolBaseNodeData extends BaseNodeData {
  description: string;
  inputSchema: NodeSchema;
  outputSchema?: NodeSchema;
  returnDirect?: boolean;
  forwardTemplate?: string;
}

// Chat input node data
export interface ChatInputNodeData extends BaseNodeData {
  inputSchema: NodeSchema;
}

// Prompt Template node data
export interface TemplateNodeData extends BaseNodeData {
  template: string;
}

// Chat Output node data
export type ChatOutputNodeData = BaseNodeData;

// Slack Output node data
export interface SlackOutputNodeData extends BaseNodeData {
  channel: string; // target Slack channel or user ID/email
  message: string; // the most recent message to send to Slack
  app_settings_id?: string; // ID of the app setting to use for this node
}

// Whatsapp Output Node Data
export interface WhatsappNodeData extends BaseNodeData {
  recipient_number?: string;
  message?: string;
  app_settings_id?: string; // ID of the app setting to use for this node
}

export interface RouterNodeData extends BaseNodeData {
  first_value?: string;
  compare_condition?:
    | "equal"
    | "not_equal"
    | "contains"
    | "not_contain"
    | "starts_with"
    | "not_starts_with"
    | "ends_with"
    | "not_ends_with"
    | "regex";
  second_value?: string;
}

export interface AggregatorNodeData extends BaseNodeData {
  aggregationStrategy?: "list" | "merge" | "first" | "last";
  timeoutSeconds?: number;
  forwardTemplate?: string;
}

export interface ZendeskTicketNodeData extends BaseNodeData {
  subject: string;
  description: string;
  requester_name?: string;
  requester_email?: string;
  tags?: string[];
  custom_fields?: Array<{ id: number; value: string | number }>;
  app_settings_id?: string;
}

export type GmailOperation =
  | "send_email"
  | "get_messages"
  | "mark_as_read"
  | "delete_message"
  | "reply_to_email"
  | "search_emails";

export interface GmailNodeData extends BaseNodeData {
  to: string; // recipient email address
  cc?: string; // optional CC email addresses
  bcc?: string; // optional BCC email addresses
  body: string; // email body content
  subject: string; // email subject line
  attachments?: string[]; // optional list of attachment file paths or URLs
  tags?: string[];
  custom_fields?: Array<{ id: number; value: string | number }>;
  dataSourceId: string; // ID of the data source to use for this node
  operation?: GmailOperation;
}

export interface SearchCriteria {
  from?: string;
  to?: string;
  subject?: string;
  has_attachment?: boolean;
  is_unread?: boolean;
  label?: string;
  newer_than?: string;
  older_than?: string;
  custom_query?: string;
  max_results?: number;
}
export interface ReadMailsNodeData extends BaseNodeData {
  searchCriteria?: SearchCriteria;
  dataSourceId?: string; // ID of the data source to use for this node
}

// API Tool Node Data
export interface APIToolNodeData extends BaseNodeData {
  endpoint: string;
  method: string;
  headers: Record<string, string>;
  parameters: Record<string, string>;
  requestBody: string;
}

// LLM Model node data
export interface BaseLLMNodeData extends BaseNodeData {
  providerId: string;
  memory: boolean;
  systemPrompt?: string;
  userPrompt?: string;
  type:
    | "Base"
    | "ReActAgent"
    | "ToolSelector"
    | "Chain-of-Thought"
    | "ReActAgentLC";
  maxIterations?: number;
}
// Agent Node Data
export interface AgentNodeData extends BaseLLMNodeData {
  type: "ReActAgent" | "ToolSelector" | "Chain-of-Thought" | "ReActAgentLC";
}
export interface LLMModelNodeData extends BaseLLMNodeData {
  type: "Base" | "Chain-of-Thought";
}
// Knowledge Base Node Data
export interface KnowledgeBaseNodeData extends BaseNodeData {
  selectedBases: string[];
  query: string;
  limit?: number;
  force?: boolean;
}

// SQL Node Data
export interface SQLNodeData extends BaseNodeData {
  providerId: string;
  dataSourceId: string;
  query: string;
  systemPrompt?: string;
  parameters?: Record<string, string>;
}

// OpenAPI Node Data
export interface OpenApiNodeData extends BaseNodeData {
  providerId: string;
  query: string;
  originalFileName: string;
  serverFilePath?: string;
}

// Python Code Node Data
export interface PythonCodeNodeData extends BaseNodeData {
  code: string;
}

// Tool Builder Node Data
export type ToolBuilderNodeData = ToolBaseNodeData;

export interface DataMapperNodeData extends BaseNodeData {
  pythonScript: string;
}

export interface CalendarEventToolNodeData extends BaseNodeData {
  summary: string; // event summary/title
  start: string; // start datetime of event
  end: string; // end datetime of event
  operation: string; // operation
  dataSourceId: string;
  subjectContains: string;
}

// Jira Node Data
export interface JiraNodeData extends BaseNodeData {
  url: string;
  email: string;
  apiToken: string;
  spaceKey: string;
  taskName: string;
  taskDescription: string;
  app_settings_id?: string;
}

// ML Model Inference Node Data
export interface MLModelInferenceNodeData extends BaseNodeData {
  modelId: string; // ID of the selected ML model
  modelName?: string; // Name of the selected model (for display)
  inferenceInputs: Record<string, string>; // Dynamic inputs based on model's inference_params
}

// Train Data Source Node Data
export interface TrainDataSourceNodeData extends BaseNodeData {
  sourceType: "datasource" | "csv"; // Type of data source
  dataSourceId?: string; // ID of the datasource (for timedb/snowflake)
  dataSourceType?: string; // Type of datasource (timedb/snowflake)
  query?: string; // SQL query to fetch data
  csvFileName?: string; // Name of the uploaded CSV file
  csvFilePath?: string; // Server path to the uploaded CSV file
}

// Preprocessing Node Data
export interface PreprocessingNodeData extends BaseNodeData {
  pythonCode: string; // Python code for data preprocessing
  fileUrl?: string; // URL to the file for preprocessing
  analysisResult?: CSVAnalysisResult; // Initial CSV analysis result (for backward compatibility)
  stepAnalysisResults?: Record<string, CSVAnalysisResult>; // Analysis results for each step (keyed by step ID or "initial")
}

// Train Model Node Data
export interface TrainModelNodeData extends BaseNodeData {
  fileUrl?: string; // URL to the CSV file for training
  analysisResult?: CSVAnalysisResult; // CSV analysis result
  modelType:
    | "xgboost"
    | "random_forest"
    | "linear_regression"
    | "logistic_regression"
    | "neural_network"
    | "other";
  targetColumn: string; // Target variable column name
  featureColumns: string[]; // Feature column names
  modelParameters: Record<string, any>; // Model-specific parameters
  validationSplit: number; // Train/validation split ratio
}

// Per Chat RAG Node Data
export interface ThreadRAGNodeData extends BaseNodeData {
  action: "retrieve" | "add";
  // For retrieve action
  query?: string;
  top_k?: number;
  // For add action
  message?: string;
}

// MCP Node Data
export interface MCPTool {
  name: string;
  description: string;
  inputSchema?: NodeSchema;
}

// Connection configuration types
export type MCPConnectionType = "stdio" | "sse" | "http";

export interface STDIOConnectionConfig {
  command: string; // Required: Command to run
  args?: string[]; // Optional: Command arguments
  env?: Record<string, string>; // Optional: Environment variables
}

export interface HTTPConnectionConfig {
  url: string; // Required: Server URL
  api_key?: string; // Optional: API key for auth
  headers?: Record<string, string>; // Optional: Custom headers
  timeout?: number; // Optional: Timeout in seconds
}

export type MCPConnectionConfig = STDIOConnectionConfig | HTTPConnectionConfig;

export interface MCPNodeData extends ToolBaseNodeData {
  connectionType: MCPConnectionType; // Required: Type of connection
  connectionConfig: MCPConnectionConfig; // Required: Configuration based on connection type
  availableTools: MCPTool[];
  whitelistedTools: string[]; // Array of tool names to expose
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
  | SQLNodeData
  | PythonCodeNodeData
  | DataMapperNodeData
  | SlackOutputNodeData
  | WhatsappNodeData
  | RouterNodeData
  | AggregatorNodeData
  | ToolBuilderNodeData
  | CalendarEventToolNodeData
  | JiraNodeData
  | MLModelInferenceNodeData
  | TrainDataSourceNodeData
  | PreprocessingNodeData
  | TrainModelNodeData
  | ThreadRAGNodeData
  | MCPNodeData;
// Node type definition
export interface NodeTypeDefinition<T extends NodeData> {
  type: string;
  label: string;
  description: string;
  shortDescription?: string;
  configSubtitle?: string;
  category:
    | "io"
    | "ai"
    | "routing"
    | "integrations"
    | "formatting"
    | "tools"
    | "training";
  icon: string;
  defaultData: T;
  component: ComponentType<NodeProps<NodeData>>; // React component for the node
  createNode: (id: string, position: { x: number; y: number }, data: T) => Node;
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
