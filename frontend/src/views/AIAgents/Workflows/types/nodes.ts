import { Edge, Node, NodeProps } from "reactflow";
import { ComponentType } from "react";
import { NodeSchema } from "./schemas";
import { CSVAnalysisResult } from "@/services/mlModels";

// Define compatibility types
export type NodeCompatibility =
  | "text"
  | "tools"
  | "llm"
  | "json"
  | "audio"
  | "sub_agents"
  | "any";

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
  // When true, the node is bypassed at execution time: the engine forwards the
  // upstream node's output straight to the downstream node(s), as if this node
  // were not present. Persisted inside the node's `data` (workflows.nodes JSONB).
  deactivated?: boolean;
  updateNodeData?: <T extends BaseNodeData>(
    nodeId: string,
    data: Partial<T>,
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

// Human In The Loop node data — collects structured data from the user mid-flow
export interface HumanInTheLoopFormField {
  name: string;
  type: "text" | "number" | "select" | "boolean" | "date";
  label: string;
  required?: boolean;
  placeholder?: string;
  description?: string;
  options?: Array<{ value: string; label: string }>;
}

export interface HumanInTheLoopNodeData extends BaseNodeData {
  message?: string;
  form_fields: HumanInTheLoopFormField[];
  ask_once?: boolean;
}

// Prompt Template node data
export interface TemplateNodeData extends BaseNodeData {
  template: string;
}

// Chat Output node data
export type ChatOutputNodeData = BaseNodeData;

// Finalize Conversation ("End Conversation") node data — pass-through, optional display name only
export type FinalizeConversationNodeData = BaseNodeData;

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
  /** Stored as boolean; string "true"/"false" may appear from older persisted JSON. */
  smartModeEnabled?: boolean | string;
  providerId?: string;
  smartPrompt?: string;
  systemPrompt?: string;
  /** Must be "true" or "false" when Smart Mode is on; invalid values normalize to "false" at runtime. */
  fallbackRoute?: string;
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

// NLP (Text Analysis) node data — unified classify/sentiment/extract/summarize
export interface NlpNodeData extends BaseNodeData {
  providerId?: string;
  inputField?: string;
  task?: "classify" | "sentiment" | "extract" | "summarize";
  // task === "classify"
  categories?: string[];
  multiLabel?: boolean;
  // task === "sentiment"
  scale?: "1-5" | "1-10";
  // task === "extract"
  schema?: string;
  // task === "summarize"
  maxLength?: number;
  style?: "concise" | "bullets" | "detailed";
}

export interface AggregatorNodeData extends BaseNodeData {
  aggregationStrategy?: "list" | "merge" | "first" | "last";
  timeoutSeconds?: number;
  forwardTemplate?: string;
  requireAllInputs?: boolean;
}

export interface ZendeskTicketNodeData extends BaseNodeData {
  subject: string;
  description: string;
  requester_name?: string;
  requester_email?: string;
  tags?: string[];
  custom_fields?: Array<{ id: string; value: string | number }>;
  app_settings_id?: string;
}

export interface SalesforceCaseNodeData extends BaseNodeData {
  subject: string;
  description: string;
  /** Assigned to the created Case as SalesForce Topics. */
  labels?: string[];
  custom_fields?: Array<{ key: string; value: string }>;
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

// Web Scraper Node Data
export type WebScraperFormat = "markdown" | "html" | "both";
export type WebScraperScreenshot = "off" | "viewport" | "fullPage";

export interface WebScraperNodeData extends BaseNodeData {
  url: string;
  format: WebScraperFormat;
  headers: Record<string, string>;
  onlyMainContent: boolean;
  screenshot: WebScraperScreenshot;
  waitFor: number;
  scrollToBottom: boolean;
  maxAge: number;
}

// Web Search Node Data
export type WebSearchDepth = "basic" | "advanced";

export interface WebSearchNodeData extends BaseNodeData {
  query: string;
  maxResults: number;
  searchDepth: WebSearchDepth;
  includeDomains: string;
  excludeDomains: string;
  maxContentChars: number;
  maxTotalContentChars: number;
  maxAge: number;
}

// HTML to Image Node Data
export type HtmlToImageCaptureMode = "fullPage" | "viewport";

export interface HtmlToImageNodeData extends BaseNodeData {
  html: string;
  captureMode: HtmlToImageCaptureMode;
  viewportWidth: number;
  viewportHeight: number;
  waitFor: number;
}

// External Agent Node Data
export interface ExternalAgentNodeData extends BaseNodeData {
  endpoint: string;
  method: string;
  headers: Record<string, string>;
  requestBody: string;
  authType: "none" | "bearer" | "api_key" | "basic";
  authToken?: string;
  authHeader?: string;
  authUsername?: string;
  authPassword?: string;
  timeout?: number;
  messageField: string;
  stepsField?: string;
  mappingScript?: string;
}

// LLM Model node data
export interface BaseLLMNodeData extends BaseNodeData {
  providerId: string;
  fallbackChainId?: string;
  memory: boolean;
  piiMasking?: boolean;
  systemPrompt?: string;
  userPrompt?: string;
  type:
    | "Base"
    | "ReActAgent"
    | "ToolSelector"
    | "Chain-of-Thought"
    | "ReActAgentLC";
  maxIterations?: number;
  memoryTrimmingMode?: "message_count" | "token_budget" | "message_compacting" | "rag_retrieval";
  maxMessages?: number;
  tokenBudget?: number;
  conversationHistoryTokens?: number;
  compactingThreshold?: number;
  compactingKeepRecent?: number;
  compactingModel?: string;
  compactingImportantEntities?: string[];
  ragPassthroughThreshold?: number;
  ragGroupSize?: number;
  ragGroupOverlap?: number;
  ragQueryContextMessages?: number;
  ragTopK?: number;
  ragRecentMessages?: number;
  ragMaxHistoryHours?: number;
  ragVectorConfig?: Record<string, unknown>;
}
// Agent Node Data
export interface AgentNodeData extends BaseLLMNodeData {
  type: "ReActAgent" | "ToolSelector" | "Chain-of-Thought" | "ReActAgentLC";
}
/** Collaboration mode controlling how control returns to the parent */
export type SubAgentMode = "single_turn" | "task" | "chat";

// Sub-Agent Node Data (a specialist child a parent agent delegates to)
export interface SubAgentNodeData extends BaseLLMNodeData {
  type: "ReActAgent" | "ToolSelector" | "ReActAgentLC";
  mode: SubAgentMode;
  /** Shown to the parent agent so it knows when to delegate */
  description: string;
  /** Seconds the parent waits for one delegated turn (5–300) */
  timeoutSeconds?: number;
}
// Voice Agent Node Data (native speech-to-speech via Gemini Live API)
export interface VoiceAgentNodeData extends BaseNodeData {
  voiceProviderId?: string;
  model?: string;
  voice?: string;
  language?: string;
  systemPrompt?: string;
  userPrompt?: string;
  maxToolCalls?: number;
  memory: boolean;
  piiMasking?: boolean;
  memoryTrimmingMode?: "message_count" | "rag_retrieval";
  maxMessages?: number;
  // Live tuning (optional; unset = Gemini Live defaults)
  temperature?: number;
  maxOutputTokens?: number;
  vadSilenceMs?: number;
  vadStartSensitivity?: "START_SENSITIVITY_HIGH" | "START_SENSITIVITY_LOW";
  vadEndSensitivity?: "END_SENSITIVITY_HIGH" | "END_SENSITIVITY_LOW";
  proactiveAudio?: boolean;
  contextCompression?: boolean;
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

// Create Workflow Schedule node data
export interface CreateWorkflowScheduleNodeData extends BaseNodeData {
  agentId: string;
  scheduleName?: string;
  cronSchedule: string;
  isActive?: boolean;
  threadIdMode?: "per_run" | "fixed";
  fixedThreadId?: string;
  message?: string;
  inputData?: string;
}

// SQL Node Data
export type SQLMode = "sqlQuery" | "humanQuery";

export interface SQLNodeData extends BaseNodeData {
  dataSourceId: string;
  mode?: SQLMode;
  sqlQuery?: string;
  providerId?: string;
  systemPrompt?: string;
  humanQuery?: string;
  parameters?: Record<string, string>;
}

// OpenAPI Node Data
export interface OpenApiNodeData extends BaseNodeData {
  providerId: string;
  query: string;
  originalFileName: string;
  serverFilePath?: string;
  serverFileUrl?: string;
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

// Set State Node Data
export interface SetStateNodeData extends BaseNodeData {
  states?: Array<{
    key: string; // The key of the stateful parameter to set
    value: string; // The value to set (can contain {{variables}})
  }>;
}

export interface CalendarEventToolNodeData extends BaseNodeData {
  summary: string; // event summary/title
  start: string; // start datetime of event
  end: string; // end datetime of event
  operation: string; // operation
  dataSourceId: string;
  subjectContains: string;
  timezone: string;
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
  inferenceInputs: Record<string, string>; // Values supplied for each of the model's features
}

// Train Data Source Node Data
export interface TrainDataSourceNodeData extends BaseNodeData {
  sourceType: "datasource" | "csv"; // Type of data source
  dataSourceId?: string; // ID of the datasource (for timedb/snowflake)
  dataSourceType?: string; // Type of datasource (timedb/snowflake)
  query?: string; // SQL query to fetch data
  csvFileName?: string; // Name of the uploaded CSV file
  csvFilePath?: string; // Server path to the uploaded CSV file
  csvFileId?: string; // ID of the uploaded CSV file
  csvFileUrl?: string; // URL of the uploaded CSV file
  analysisResult?: CSVAnalysisResult; // Preview/analysis of the uploaded file
}

// Preprocessing Node Data
export interface PreprocessingNodeData extends BaseNodeData {
  pythonCode: string; // Python code for data preprocessing
  fileUrl?: string; // URL to the file for preprocessing
  analysisResult?: CSVAnalysisResult; // Initial CSV analysis result (for backward compatibility)
  stepAnalysisResults?: Record<string, CSVAnalysisResult>; // Analysis results for each step (keyed by step ID or "initial")
}

// Train Model Node Data
export type SplitMethod = "random" | "time_based";

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
  splitMethod?: SplitMethod; // How to split train/validation data (default: "random")
  dateColumn?: string; // Date/timestamp column to sort by when splitMethod is "time_based"
}

// Per Chat RAG Node Data
export interface ThreadRAGNodeData extends BaseNodeData {
  action: "retrieve" | "add";
  // For retrieve action
  query?: string;
  top_k?: number;
  // For add action
  message?: string;
  // Vector store config (embedding, vector DB, chunking)
  ragVectorConfig?: Record<string, unknown>;
}

// MCP Node Data
export interface MCPTool {
  name: string;
  description: string;
  inputSchema?: NodeSchema;
}

// Connection configuration types
export type MCPConnectionType = "stdio" | "sse" | "http";

export type MCPAuthType = "api_key" | "oauth2" | "none";
export type MCPOAuth2Flow = "client_credentials";

export interface STDIOConnectionConfig {
  command: string; // Required: Command to run
  args?: string[]; // Optional: Command arguments
  env?: Record<string, string>; // Optional: Environment variables
}

export interface HTTPConnectionConfig {
  url: string; // Required: Server URL
  // --- Authentication ---
  auth_type?: MCPAuthType; // "api_key" (default) | "oauth2" | "none"
  // api_key auth
  api_key?: string;
  // oauth2 auth
  oauth2_flow?: MCPOAuth2Flow; // "client_credentials" (default)
  oauth2_client_id?: string;
  oauth2_client_secret?: string;
  /** Full openid-configuration URL — token_endpoint read from this document (preferred) */
  oauth2_issuer_url?: string;
  /** Direct token endpoint (legacy; omit when using issuer URL) */
  oauth2_token_url?: string;
  oauth2_scopes?: string[]; // e.g. ["openid", "mcp"]
  oauth2_audience?: string; // Some IdPs (Auth0, etc.) require audience on token request
  // --- General ---
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

export interface NodeHelpSection {
  title: string;
  body?: string;
  bullets?: string[];
  steps?: string[];
}

export interface NodeHelpContent {
  intro: string;
  sections?: NodeHelpSection[];
}

// Workflow Executor Node Data
export interface WorkflowExecutorNodeData extends BaseNodeData {
  workflowId?: string; // ID of the selected workflow to execute
  workflowName?: string; // Name of the selected workflow (for display)
  inputParameters: Record<string, string>; // Input parameters for the workflow
}

// Guardrail Provenance Node Data
export interface GuardrailProvenanceNodeData extends BaseNodeData {
  answer_field?: string;
  context_field?: string;
  min_score?: number;
  fail_on_violation?: boolean;
  fallback_answer_enabled?: boolean;
  fallback_answer?: string;
  use_llm_judge?: boolean;
  llm_provider_id?: string;
  provenance_mode?: "embeddings" | "llm";
  embedding_type?: "openai" | "huggingface" | "bedrock";
  embedding_model_name?: string;
  llm_judge_system_prompt_suffix?: string;
}

// Guardrail NLI Node Data
export interface GuardrailNliNodeData extends BaseNodeData {
  answer_field?: string;
  evidence_field?: string;
  min_entail_score?: number;
  fail_on_contradiction?: boolean;
  fallback_answer_enabled?: boolean;
  fallback_answer?: string;
  nli_model_name?: string;
}

// File Reader Node Data
export interface FileReaderNodeData extends BaseNodeData {
  fileSource?: "chatAttachment" | "upload";
  fileName?: string;
  filePath?: string;
  fileUrl?: string;
  fileId?: string;
}

// TTS Node Data
export interface TTSNodeData extends BaseNodeData {
  text: string;
  provider: string;
  audioProviderId?: string;
  voice: string;
  model: string;
  output_format: string;
  speed: number;
}

// STT Node Data
export interface STTNodeData extends BaseNodeData {
  audio_source: string;
  provider: string;
  audioProviderId?: string;
  model: string;
  language?: string;
  response_format: string;
  temperature: number;
}

// Union type for all node data types
export type NodeData =
  | ChatInputNodeData
  | LLMModelNodeData
  | TemplateNodeData
  | ChatOutputNodeData
  | FinalizeConversationNodeData
  | APIToolNodeData
  | AgentNodeData
  | SubAgentNodeData
  | KnowledgeBaseNodeData
  | SQLNodeData
  | PythonCodeNodeData
  | DataMapperNodeData
  | SlackOutputNodeData
  | WhatsappNodeData
  | RouterNodeData
  | NlpNodeData
  | AggregatorNodeData
  | ToolBuilderNodeData
  | CalendarEventToolNodeData
  | JiraNodeData
  | MLModelInferenceNodeData
  | TrainDataSourceNodeData
  | PreprocessingNodeData
  | TrainModelNodeData
  | ThreadRAGNodeData
  | MCPNodeData
  | WorkflowExecutorNodeData
  | HumanInTheLoopNodeData
  | SetStateNodeData
  | GuardrailProvenanceNodeData
  | GuardrailNliNodeData
  | FileReaderNodeData
  | ExternalAgentNodeData
  | TTSNodeData
  | STTNodeData
  | VoiceAgentNodeData
  | WebScraperNodeData
  | HtmlToImageNodeData
  | WebSearchNodeData;
// Node type definition
export interface NodeTypeDefinition<T extends NodeData> {
  type: string;
  label: string;
  description: string;
  shortDescription?: string;
  helpContent?: NodeHelpContent;
  configSubtitle?: string;
  category:
    | "io"
    | "ai"
    | "audio"
    | "routing"
    | "integrations"
    | "formatting"
    | "tools"
    | "training" | "utils"
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
  data: T,
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
  data: Record<string, unknown>,
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
