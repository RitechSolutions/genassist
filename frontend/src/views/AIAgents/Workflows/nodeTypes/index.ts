import nodeRegistry from "../registry/nodeRegistry";
import ChatInputNode from "./chat/chatInputNode";
import LLMModelNode from "./llm/modelNode";
import APIToolNode from "./tools/apiToolNode";
import OpenApiNode from "./tools/openApiNode";
import AgentNode from "./llm/agentNode";
import PythonCodeNode from "./tools/pythonCodeNode";
import {
  CHAT_INPUT_NODE_DEFINITION,
  CHAT_OUTPUT_NODE_DEFINITION,
} from "./chat/definitions";
import {
  API_TOOL_NODE_DEFINITION,
  OPEN_API_NODE_DEFINITION,
  KNOWLEDGE_BASE_NODE_DEFINITION,
  PYTHON_CODE_NODE_DEFINITION,
  SQL_NODE_DEFINITION,
  ML_MODEL_INFERENCE_NODE_DEFINITION,
  THREAD_RAG_NODE_DEFINITION,
  WORKFLOW_EXECUTOR_NODE_DEFINITION,
} from "./tools/definitions";
import KnowledgeBaseNode from "./tools/knowledgeBaseNode";
import SQLNode from "./tools/sqlNode";
import MLModelInferenceNode from "./tools/mlModelInferenceNode";
import ThreadRAGNode from "./tools/threadRAGNode";
import WorkflowExecutorNode from "./tools/workflowExecutorNode";
import MCPNode from "./llm/mcpNode";
import ReadMailsNode from "./integrations/readMailsNode";
import ToolBuilderNode from "./llm/toolBuilderNode";
import ChatOutputNode from "./chat/chatOutputNode";
import {
  AGENT_NODE_DEFINITION,
  MODEL_NODE_DEFINITION,
  TOOL_BUILDER_NODE_DEFINITION,
  MCP_NODE_DEFINITION,
} from "./llm/definitions";
import {
  DATA_MAPPER_NODE_DEFINITION,
  TEMPLATE_NODE_DEFINITION,
} from "./utils/definitions";
import TemplateNode from "./utils/templateNode";
import DataMapperNode from "./utils/dataMapperNode";
import SlackOutputNode from "./integrations/slackOutputNode";
import ZendeskTicketNode from "./integrations/zendeskTicketNode";
import GmailNode from "./integrations/gmailNode";
import {
  GMAIL_NODE_DEFINITION,
  ZENDESK_TICKET_NODE_DEFINITION,
  SLACK_OUTPUT_NODE_DEFINITION,
  CALENDAR_EVENT_NODE_DEFINITION,
  READ_MAILS_NODE_DEFINITION,
  WHATSAPP_NODE_DEFINITION,
  JIRA_NODE_DEFINITION,
} from "@/views/AIAgents/Workflows/nodeTypes/integrations/definition";
import WhatsAppNode from "./integrations/whatsappNode";
import {
  ROUTER_NODE_DEFINITION,
  AGGREGATOR_NODE_DEFINITION,
} from "./router/definitions";
import RouterNode from "./router/routerNode";
import AggregatorNode from "./router/aggregatorNode";
import CalendarEventNode from "./integrations/calendarEventNode";
import {
  TRAIN_DATA_SOURCE_NODE_DEFINITION,
  PREPROCESSING_NODE_DEFINITION,
  TRAIN_MODEL_NODE_DEFINITION,
} from "./training/definitions";
import TrainDataSourceNode from "./training/trainDataSourceNode";
import PreprocessingNode from "./training/preprocessingNode";
import TrainModelNode from "./training/trainModelNode";
import JiraNode from "./integrations/jiraNode";

// A function to re-register if needed
export const registerAllNodeTypes = () => {
  // Clear existing registry to prevent duplicates
  nodeRegistry.clearRegistry();
  nodeRegistry.registerNodeType(TEMPLATE_NODE_DEFINITION);
  nodeRegistry.registerNodeType(MODEL_NODE_DEFINITION);
  nodeRegistry.registerNodeType(API_TOOL_NODE_DEFINITION);
  nodeRegistry.registerNodeType(OPEN_API_NODE_DEFINITION);

  nodeRegistry.registerNodeType(WHATSAPP_NODE_DEFINITION);

  nodeRegistry.registerNodeType(CHAT_INPUT_NODE_DEFINITION);

  nodeRegistry.registerNodeType(SLACK_OUTPUT_NODE_DEFINITION);

  nodeRegistry.registerNodeType(CHAT_OUTPUT_NODE_DEFINITION);

  nodeRegistry.registerNodeType(ZENDESK_TICKET_NODE_DEFINITION);
  nodeRegistry.registerNodeType(GMAIL_NODE_DEFINITION);
  nodeRegistry.registerNodeType(KNOWLEDGE_BASE_NODE_DEFINITION);
  nodeRegistry.registerNodeType(SQL_NODE_DEFINITION);
  nodeRegistry.registerNodeType(ML_MODEL_INFERENCE_NODE_DEFINITION);
  nodeRegistry.registerNodeType(READ_MAILS_NODE_DEFINITION);
  nodeRegistry.registerNodeType(PYTHON_CODE_NODE_DEFINITION);
  nodeRegistry.registerNodeType(THREAD_RAG_NODE_DEFINITION);
  nodeRegistry.registerNodeType(AGENT_NODE_DEFINITION);

  nodeRegistry.registerNodeType(TOOL_BUILDER_NODE_DEFINITION);

  nodeRegistry.registerNodeType(DATA_MAPPER_NODE_DEFINITION);

  nodeRegistry.registerNodeType(ROUTER_NODE_DEFINITION);

  nodeRegistry.registerNodeType(AGGREGATOR_NODE_DEFINITION);

  nodeRegistry.registerNodeType(CALENDAR_EVENT_NODE_DEFINITION);

  nodeRegistry.registerNodeType(JIRA_NODE_DEFINITION);

  nodeRegistry.registerNodeType(TRAIN_DATA_SOURCE_NODE_DEFINITION);
  nodeRegistry.registerNodeType(PREPROCESSING_NODE_DEFINITION);
  nodeRegistry.registerNodeType(TRAIN_MODEL_NODE_DEFINITION);

  nodeRegistry.registerNodeType(MCP_NODE_DEFINITION);

  nodeRegistry.registerNodeType(WORKFLOW_EXECUTOR_NODE_DEFINITION);
};

// Get node types for React Flow
export const getNodeTypes = () => {
  return {
    chatInputNode: ChatInputNode,
    llmModelNode: LLMModelNode,
    templateNode: TemplateNode,
    chatOutputNode: ChatOutputNode,
    apiToolNode: APIToolNode,
    openApiNode: OpenApiNode,
    agentNode: AgentNode,
    knowledgeBaseNode: KnowledgeBaseNode,
    sqlNode: SQLNode,
    mlModelInferenceNode: MLModelInferenceNode,
    threadRAGNode: ThreadRAGNode,

    slackMessageNode: SlackOutputNode,
    whatsappToolNode: WhatsAppNode,
    zendeskTicketNode: ZendeskTicketNode,
    gmailNode: GmailNode,
    readMailsNode: ReadMailsNode,
    pythonCodeNode: PythonCodeNode,
    toolBuilderNode: ToolBuilderNode,
    routerNode: RouterNode,
    aggregatorNode: AggregatorNode,
    dataMapperNode: DataMapperNode,
    calendarEventNode: CalendarEventNode,
    jiraNode: JiraNode,
    trainDataSourceNode: TrainDataSourceNode,
    preprocessingNode: PreprocessingNode,
    trainModelNode: TrainModelNode,
    mcpNode: MCPNode,
    workflowExecutorNode: WorkflowExecutorNode,
  };
};
