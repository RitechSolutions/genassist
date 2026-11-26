import { Edge, Node } from "reactflow";
import { Workflow } from "@/interfaces/workflow.interface";
import { stripTransientGraphFields } from "./graphNormalization";

// Node data left out of a workflow file: links to this server's files and rows sampled from them
export const FILE_OMITTED_DATA: Record<string, readonly string[]> = {
  fileReaderNode: ["fileId", "fileUrl", "filePath", "fileName"],
  openApiNode: ["serverFilePath", "serverFileUrl", "originalFileName"],
  preprocessingNode: ["analysisResult", "stepAnalysisResults", "analyzedFileUrl"],
  trainDataSourceNode: ["csvFilePath", "csvFileId", "csvFileUrl", "analysisResult"],
  trainModelNode: ["analysisResult"],
  agentNode: [],
  aggregatorNode: [],
  apiToolNode: [],
  calendarEventNode: [],
  chatInputNode: [],
  chatOutputNode: [],
  createWorkflowScheduleNode: [],
  dataMapperNode: [],
  externalAgentNode: [],
  filterNode: [],
  finalizeConversationNode: [],
  gmailNode: [],
  guardrailNliNode: [],
  guardrailNode: [],
  guardrailProvenanceNode: [],
  htmlToImageNode: [],
  humanInTheLoopNode: [],
  jiraNode: [],
  knowledgeBaseNode: [],
  llmModelNode: [],
  loopNode: [],
  mcpNode: [],
  mlModelInferenceNode: [],
  nlpNode: [],
  pythonCodeNode: [],
  readMailsNode: [],
  routerNode: [],
  salesforceCaseNode: [],
  setStateNode: [],
  slackMessageNode: [],
  sqlNode: [],
  sttNode: [],
  subAgentNode: [],
  switchNode: [],
  templateNode: [],
  threadRAGNode: [],
  toolBuilderNode: [],
  ttsNode: [],
  voiceAgentNode: [],
  webScraperNode: [],
  webSearchNode: [],
  webhookTriggerNode: [],
  whatsappToolNode: [],
  workflowExecutorNode: [],
  zendeskTicketNode: [],
};

const withoutOmittedData = (node: Node): Node => {
  const omitted = FILE_OMITTED_DATA[node.type ?? ""];
  if (!omitted?.length) return node;
  const data = { ...node.data };
  for (const key of omitted) delete data[key];
  return { ...node, data };
};

const cleanGraph = (nodes?: Node[] | null, edges?: Edge[] | null) => {
  const graph = stripTransientGraphFields(nodes ?? [], edges ?? []);
  return { nodes: graph.nodes.map(withoutOmittedData), edges: graph.edges };
};

export const toWorkflowFile = (
  workflow: Workflow
): Pick<Workflow, "name" | "description" | "version" | "settings" | "nodes" | "edges"> => {
  const { name, description, version, settings } = workflow;
  return { name, description, version, settings, ...cleanGraph(workflow.nodes, workflow.edges) };
};

export const graphFromWorkflowFile = (file: Pick<Workflow, "nodes" | "edges">) =>
  cleanGraph(file.nodes, file.edges);
