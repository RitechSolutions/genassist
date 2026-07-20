/**
 * Maps a workflow node `type` to its documentation page on docs.genassist.ai.
 *
 * Only nodes that currently have a published docs page are listed here. Node
 * types without an entry simply won't show the "Docs" button in their help
 * dialog. Keyed by the node definition's `type` string (see nodeTypes/*).
 */

const DOCS_BASE_URL = "https://docs.genassist.ai/nodes";

export const NODE_DOCS_URLS: Record<string, string> = {
  // Formatting
  templateNode: `${DOCS_BASE_URL}/formatting/text-template`,
  dataMapperNode: `${DOCS_BASE_URL}/formatting/data-transformer`,

  // AI
  llmModelNode: `${DOCS_BASE_URL}/ai/language-model`,
  agentNode: `${DOCS_BASE_URL}/ai/ai-agent`,
  voiceAgentNode: `${DOCS_BASE_URL}/ai/voice-agent`,
  externalAgentNode: `${DOCS_BASE_URL}/ai/external-agent`,
  toolBuilderNode: `${DOCS_BASE_URL}/ai/tool-builder`,
  mcpNode: `${DOCS_BASE_URL}/ai/mcp-server`,

  // Tools
  apiToolNode: `${DOCS_BASE_URL}/tools/api-connector`,
  openApiNode: `${DOCS_BASE_URL}/tools/openapi-explorer`,
  knowledgeBaseNode: `${DOCS_BASE_URL}/tools/knowledge-query`,
  createWorkflowScheduleNode: `${DOCS_BASE_URL}/tools/create-workflow-schedule`,
  sqlNode: `${DOCS_BASE_URL}/tools/sql-generator`,
  mlModelInferenceNode: `${DOCS_BASE_URL}/tools/ml-model-inference`,
  pythonCodeNode: `${DOCS_BASE_URL}/tools/python-executor`,
  threadRAGNode: `${DOCS_BASE_URL}/tools/thread-rag`,
  workflowExecutorNode: `${DOCS_BASE_URL}/tools/workflow-executor`,

  // Integrations
  whatsappToolNode: `${DOCS_BASE_URL}/integration/whatsapp-messenger`,
  slackMessageNode: `${DOCS_BASE_URL}/integration/slack-messenger`,
  zendeskTicketNode: `${DOCS_BASE_URL}/integration/zendesk-ticket-creator`,
  salesforceCaseNode: `${DOCS_BASE_URL}/integration/category-overview`,
  gmailNode: `${DOCS_BASE_URL}/integration/email-sender`,
  readMailsNode: `${DOCS_BASE_URL}/integration/email-reader`,
  calendarEventNode: `${DOCS_BASE_URL}/integration/calendar-scheduler`,
  jiraNode: `${DOCS_BASE_URL}/integration/jira-task-creator`,

  // I/O
  chatInputNode: `${DOCS_BASE_URL}/io/start`,
  chatOutputNode: `${DOCS_BASE_URL}/io/finish`,
  finalizeConversationNode: `${DOCS_BASE_URL}/io/end-conversation`,
  setStateNode: `${DOCS_BASE_URL}/io/set-state`,
  humanInTheLoopNode: `${DOCS_BASE_URL}/io/human-in-the-loop`,

  // Utils
  guardrailProvenanceNode: `${DOCS_BASE_URL}/utils/guardrail-provenance`,
  guardrailNliNode: `${DOCS_BASE_URL}/utils/guardrail-nli`,
  fileReaderNode: `${DOCS_BASE_URL}/utils/file-reader`,

  // Routing
  routerNode: `${DOCS_BASE_URL}/routing/conditional-router`,
  aggregatorNode: `${DOCS_BASE_URL}/routing/result-merger`,

  // Training
  trainDataSourceNode: `${DOCS_BASE_URL}/training/train-data-source`,
  preprocessingNode: `${DOCS_BASE_URL}/training/data-preprocessing`,
  trainModelNode: `${DOCS_BASE_URL}/training/train-model`,

  // Audio
  ttsNode: `${DOCS_BASE_URL}/audio/text-to-speech`,
  sttNode: `${DOCS_BASE_URL}/audio/speech-to-text`,
};

/** Returns the docs URL for a node type, or `undefined` if none is published yet. */
export const getNodeDocsUrl = (nodeType?: string): string | undefined =>
  nodeType ? NODE_DOCS_URLS[nodeType] : undefined;
