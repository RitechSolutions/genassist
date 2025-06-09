import { apiRequest } from "@/config/api";

import {
  Workflow,
  WorkflowCreatePayload,
  WorkflowUpdatePayload,
} from "@/interfaces/workflow.interface";
import {
  KnowledgeBaseNodeData,
  PythonCodeNodeData,
  SlackOutputNodeData,
  ZendeskTicketNodeData,
} from "@/views/AIAgents/Workflows/types/nodes";

const BASE = "genagent/workflow";

// Get all workflows
export const getAllWorkflows = () => apiRequest<Workflow[]>("GET", `${BASE}/`);

// Get workflow by ID
export const getWorkflowById = (id: string) =>
  apiRequest<Workflow>("GET", `${BASE}/${id}`);

// Create a new workflow
export const createWorkflow = (workflow: WorkflowCreatePayload) =>
  apiRequest<Workflow>(
    "POST",
    `${BASE}/`,
    workflow as unknown as Record<string, unknown>
  );

// Update an existing workflow
export const updateWorkflow = (id: string, workflow: WorkflowUpdatePayload) =>
  apiRequest<Workflow>(
    "PUT",
    `${BASE}/${id}`,
    workflow as unknown as Record<string, unknown>
  );

// Delete a workflow
export const deleteWorkflow = (id: string) =>
  apiRequest<void>("DELETE", `${BASE}/${id}`);

// Test a workflow configuration with a test message
export interface WorkflowTestPayload {
  message: string;
  session: any;
  workflow: Workflow;
}

export interface WorkflowTestResponse {
  status: string;
  input: string;
  output: string;
  workflow_id: string | null;
  execution_summary: {
    execution_id: string;
    thread_id: string;
    timestamp: string;
    execution_path: string[];
    input: string;
    node_outputs: {
      [key: string]:
        | string
        | {
            status: number;
            data: Array<{
              id: string;
              name: string;
              data: Record<string, any> | null;
            }>;
          };
    };
  };
}

export const testWorkflow = (testData: WorkflowTestPayload) =>
  apiRequest<WorkflowTestResponse>(
    "POST",
    `${BASE}/test`,
    testData as unknown as Record<string, unknown>
  );

export const slackMessageOutput = (
  message: string,
  slackNodeData: Pick<
    SlackOutputNodeData,
    "name" | "token" | "channel" | "handlers"
  >
) =>
  apiRequest<SlackOutputNodeData>("POST", `${BASE}/slack-output-message`, {
    slack_token: slackNodeData.token,
    slack_channel: slackNodeData.channel,
    slack_message: message,
  } as Record<string, unknown>);

export const zendeskTicketOutput = (
  data: Pick<
    ZendeskTicketNodeData,
    "subject" | "description" | "requester_name" | "requester_email" | "tags"
  >
) =>
  apiRequest<{ status: number; data: any }>(
    "POST",
    `${BASE}/zendesk-output-message`,
    data as Record<string, unknown>
  );
  
export const testKnowledgeBase = (
  query: string,
  knowledgeNodeData: KnowledgeBaseNodeData
) =>
  apiRequest<WorkflowTestResponse>("POST", `${BASE}/test-knowledge-tool`, {
    tool_config: knowledgeNodeData,
    query,
  } as unknown as Record<string, unknown>);

export const testPythonCode = (
  pythonCodeNodeData: PythonCodeNodeData,
  input_params: Record<string, any>
) =>
  apiRequest<{
    result: any;
    original_params: any;
    validated_params: any;
  }>("POST", `${BASE}/test-python-function`, {
    tool_config: pythonCodeNodeData,
    input_params,
  } as unknown as Record<string, unknown>);

export const generatePythonTemplate = (schema: any) =>
  apiRequest<{ template: string }>("POST", `${BASE}/generate-python-template`, {
    parameters_schema: schema,
  } as unknown as Record<string, unknown>);
