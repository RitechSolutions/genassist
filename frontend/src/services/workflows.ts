import { apiRequest } from "@/config/api";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

import {
  Workflow,
  WorkflowCreatePayload,
  WorkflowUpdatePayload,
} from "@/interfaces/workflow.interface";
import { NodeData } from "@/views/AIAgents/Workflows/types/nodes";

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
  input_data: Record<string, any>;
  workflow: Workflow;
}

export interface WorkflowTestResponse {
  status: string;
  input: string;
  output: string;
  [key: string]: any;
}

export interface NodeTestPayload {
  input_data: Record<string, any>;
  node_type: string;
  node_config: NodeData;
}

export const getNodeDialogSchema = async (
  nodeType: string
): Promise<FieldSchema[]> => {
  try {
    return await apiRequest<FieldSchema[]>(
      "GET",
      `${BASE}/dialog_schema/${nodeType}`
    );
  } catch (error) {
    console.error("Error fetching node dialog schema", error);
    throw error;
  }
};

export const testNode = (testData: NodeTestPayload) =>
  apiRequest<WorkflowTestResponse>(
    "POST",
    `${BASE}/test-node`,
    testData as unknown as Record<string, unknown>
  );

export const testWorkflow = (testData: WorkflowTestPayload) =>
  apiRequest<WorkflowTestResponse>(
    "POST",
    `${BASE}/test`,
    testData as unknown as Record<string, unknown>
  );

export const generatePythonTemplate = (schema: any, prompt?: string) =>
  apiRequest<{ template: string }>("POST", `${BASE}/generate-python-template`, {
    parameters_schema: schema,
    prompt,
  } as unknown as Record<string, unknown>);
