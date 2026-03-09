const NODE_TYPE_LABELS: Record<string, string> = {
  // LLM
  agentNode: "AI Agent",
  llmModelNode: "Language Model",
  toolBuilderNode: "Tool Builder",
  mcpNode: "MCP Server",
  // Chat / IO
  chatInputNode: "Start",
  chatOutputNode: "Finish",
  setStateNode: "Set State",
  humanInTheLoopNode: "Human In The Loop",
  userInputNode: "User Input",
  // Tools
  apiToolNode: "API Connector",
  openApiNode: "OpenAPI Explorer",
  knowledgeBaseNode: "Knowledge Query",
  pythonCodeNode: "Python Executor",
  sqlNode: "SQL Executor",
  mlModelInferenceNode: "ML Model Inference",
  threadRAGNode: "Thread RAG",
  workflowExecutorNode: "Workflow Executor",
  // Router
  routerNode: "Conditional Router",
  aggregatorNode: "Result Merger",
  // Utils
  templateNode: "Text Template",
  dataMapperNode: "Data Transformer",
  // Training
  trainDataSourceNode: "Train Data Source",
  preprocessingNode: "Data Preprocessing",
  trainModelNode: "Train Model",
  // Integrations
  gmailNode: "Email Sender",
  readMailsNode: "Email Reader",
  slackMessageNode: "Slack Messenger",
  whatsappToolNode: "WhatsApp Messenger",
  zendeskTicketNode: "Zendesk Ticket Creator",
  calendarEventNode: "Calendar Scheduler",
  jiraNode: "Jira Task Creator",
};

/** Returns a human-friendly label for a workflow node type. Falls back to splitting camelCase. */
export function nodeTypeLabel(type: string): string {
  if (NODE_TYPE_LABELS[type]) return NODE_TYPE_LABELS[type];
  // Fallback: split camelCase, remove trailing "Node", capitalise each word
  return type
    .replace(/([A-Z])/g, " $1")
    .replace(/\bNode\b/gi, "")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
