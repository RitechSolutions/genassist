import nodeRegistry from "../registry/nodeRegistry";
import ChatInputNode from "./chat/chatInputNode";
import LLMModelNode from "./llm/modelNode";
import APIToolNode from "./tools/apiToolNode";
import AgentNode from "./llm/agentNode";
import PythonCodeNode from "./tools/pythonCodeNode";
import { CHAT_INPUT_NODE_DEFINITION, CHAT_OUTPUT_NODE_DEFINITION, SLACK_OUTPUT_NODE_DEFINITION } from "./chat/definitions";
import { API_TOOL_NODE_DEFINITION, KNOWLEDGE_BASE_NODE_DEFINITION, PYTHON_CODE_NODE_DEFINITION } from "./tools/definitions";
import KnowledgeBaseNode from "./tools/knowledgeBaseNode";
import ChatOutputNode from "./chat/chatOutputNode";
import { AGENT_NODE_DEFINITION, MODEL_NODE_DEFINITION } from "./llm/definitions";
import { TEMPLATE_NODE_DEFINITION } from "./utils/definitions";
import TemplateNode from "./utils/templateNode";
import SlackOutputNode from "./chat/slackOutputNode";
import ZendeskTicketNode from "./zendesk/zendeskTicketNode";
import { ZENDESK_TICKET_NODE_DEFINITION } from "@/views/AIAgents/Workflows/nodeTypes/zendesk/definitions";


// A function to re-register if needed
export const registerAllNodeTypes = () => {
  // Clear existing registry to prevent duplicates
  nodeRegistry.clearRegistry();

  // Register ChatInput node
  nodeRegistry.registerNodeType(CHAT_INPUT_NODE_DEFINITION);


    // Register Slack Message Output node
  nodeRegistry.registerNodeType(SLACK_OUTPUT_NODE_DEFINITION);

  nodeRegistry.registerNodeType(CHAT_OUTPUT_NODE_DEFINITION);
  // Register API Tool node
  nodeRegistry.registerNodeType(API_TOOL_NODE_DEFINITION);
      // Register Zendesk node
  nodeRegistry.registerNodeType(ZENDESK_TICKET_NODE_DEFINITION);
  // Register Knowledge Base node
  nodeRegistry.registerNodeType(KNOWLEDGE_BASE_NODE_DEFINITION);
  // Register Python Code node
  nodeRegistry.registerNodeType(PYTHON_CODE_NODE_DEFINITION);
  // Register LLM Model node
  nodeRegistry.registerNodeType(MODEL_NODE_DEFINITION);
  // Register Prompt Template node
  nodeRegistry.registerNodeType(TEMPLATE_NODE_DEFINITION);
  // Register Agent node
  nodeRegistry.registerNodeType(AGENT_NODE_DEFINITION);

};

// Get node types for React Flow
export const getNodeTypes = () => {
  return {
    chatInputNode: ChatInputNode,
    llmModelNode: LLMModelNode,
    promptNode: TemplateNode,
    chatOutputNode: ChatOutputNode,
    apiToolNode: APIToolNode,
    agentNode: AgentNode,
    knowledgeBaseNode: KnowledgeBaseNode,

    slackMessageNode: SlackOutputNode, 
    zendeskTicketNode: ZendeskTicketNode,
    pythonCodeNode: PythonCodeNode,
  };
};
