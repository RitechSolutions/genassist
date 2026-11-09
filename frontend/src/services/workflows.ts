import { apiRequest, API_WORKFLOW_TEST_TIMEOUT_MS } from "@/config/api";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";
import { KEEPALIVE_HEADERS, throwIfErrorEnvelope } from "@/helpers/apiError";

import {
  Workflow,
  WorkflowCreatePayload,
  WorkflowMinimal,
  WorkflowSummary,
  WorkflowUpdatePayload,
} from "@/interfaces/workflow.interface";
import { NodeData } from "@/views/AIAgents/Workflows/types/nodes";

const BASE = "genagent/workflow";

// Get all workflows
export const getAllWorkflows = () => apiRequest<Workflow[]>("GET", `${BASE}/`);

// Get lightweight workflow list (id, name, version only)
export const getWorkflowsMinimal = () =>
  apiRequest<WorkflowMinimal[]>("GET", `${BASE}/minimal`);

export const getWorkflowSummaries = (agentId: string) =>
  apiRequest<WorkflowSummary[]>(
    "GET",
    `${BASE}/summaries?agent_id=${encodeURIComponent(agentId)}`
  );

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
  apiRequest<void>(
    "DELETE",
    `${BASE}/${id}`,
    undefined,
    {},
    { rethrowForbidden: true }
  );

// Test a workflow configuration with a test message
export interface WorkflowTestPayload {
  input_data: Record<string, any>;
  workflow: Workflow;
}

/** A node that reported a failure during the run (e.g. an API/tool node whose
 *  request completed but did not do its job). The run still completes. */
export interface FailedNode {
  node_id: string;
  name: string;
  type: string;
  error: string;
}

/** Per-run token totals. Counts are provider-reported, so cache buckets may or may not
 *  be contained in input_tokens depending on the provider. */
export interface WorkflowTokenUsage {
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  cache_read_tokens?: number;
  cache_creation_tokens?: number;
  cost_usd?: number;
  /** True when a call could not be priced, so cost_usd is the priced subtotal only. */
  cost_is_partial?: boolean;
  fallback_calls?: number;
  fallback_models?: string[];
  calls?: number;
}

export interface WorkflowTestResponse {
  /** "success", "partial", "failed" or "awaiting_input" - see workflowRunOutcome. */
  status: string;
  input: string;
  output: string;
  /** True when one or more nodes failed (status is then "partial" or "failed"). */
  has_failures?: boolean;
  /** Details of the nodes that failed, if any. */
  failed_nodes?: FailedNode[];
  token_usage?: WorkflowTokenUsage;
  [key: string]: any;
}

/**
 * How a run ended: "success" (no node failed), "partial" (a node failed but the
 * run still produced a response), "failed", or "awaiting_input" (paused for the
 * user). Older backends sent "success" with has_failures for a run where a node
 * failed; that reads as "partial".
 */
export type WorkflowRunOutcome = "success" | "partial" | "failed" | "awaiting_input";

export const workflowRunOutcome = (response: WorkflowTestResponse | null | undefined): WorkflowRunOutcome => {
  switch (response?.status) {
    case "awaiting_input":
    case "partial":
    case "failed":
      return response.status;
    case "success":
      return response.has_failures ? "partial" : "success";
    default:
      return "failed";
  }
};

export const TRAIN_DATA_SOURCE_NODE_TYPE = "trainDataSourceNode";
export const TRAIN_DATA_SOURCE_TEST_FALLBACK =
  "Train Data Source could not complete the test. Check its configuration and try again.";

const stripEngineNodePrefix = (error: string): string =>
  error.replace(/^Error executing node [^:]+:\s*/, "").trim();

/** Format a failed node consistently in both workflow-test surfaces. */
export const getFailedNodeDisplayMessage = (failedNode: FailedNode): string => {
  const error = failedNode.error?.trim() ?? "";
  if (failedNode.type !== TRAIN_DATA_SOURCE_NODE_TYPE) return error;

  return stripEngineNodePrefix(error) || TRAIN_DATA_SOURCE_TEST_FALLBACK;
};

/**
 * Return the client-safe failure reported by a Train Data Source node test.
 * Other node failures are deliberately ignored so this behavior stays scoped
 * to the Train Data Source dialog.
 */
export const getTrainDataSourceTestFailureMessage = (
  response: WorkflowTestResponse | null
): string | null => {
  const failedNode = response?.failed_nodes?.find(
    (node) => node.type === TRAIN_DATA_SOURCE_NODE_TYPE
  );

  if (!failedNode) return null;

  return getFailedNodeDisplayMessage(failedNode);
};

/**
 * The errors that stopped a run outside any node ("execution_failure" entries
 * in state.errors, as the backend's execution_failures()), each once.
 */
export const getEngineErrors = (response: WorkflowTestResponse | null | undefined): string[] => {
  const errors: unknown[] = Array.isArray(response?.state?.errors) ? response.state.errors : [];
  const messages = errors
    .filter(
      (e): e is { message?: unknown } =>
        typeof e === "object" && e !== null && (e as { type?: unknown }).type === "execution_failure"
    )
    .map((e) => String(e.message ?? ""))
    .filter(Boolean);
  return Array.from(new Set(messages));
};

/** The error to show when a node test failed (status "failed"), or null. */
export const getNodeTestFailureMessage = (response: WorkflowTestResponse | null): string | null => {
  if (!response || workflowRunOutcome(response) !== "failed") return null;
  const failedNode = response.failed_nodes?.[0];
  return (
    (failedNode && getFailedNodeDisplayMessage(failedNode)) ||
    getEngineErrors(response).join("; ") ||
    "The node failed. Check its configuration and try again."
  );
};

export interface NodeTestPayload {
  input_data: Record<string, any>;
  node_type: string;
  node_config: NodeData;
}

export interface NodeSchemas {
  [nodeType: string]: FieldSchema[];
}

export const getAllNodeSchemas = async (): Promise<NodeSchemas> => {
  try {
    return await apiRequest<NodeSchemas>("GET", `${BASE}/node_schemas`);
  } catch (error) {
    console.error("Error fetching all node schemas", error);
    throw error;
  }
};

export const testNode = (testData: NodeTestPayload) =>
  apiRequest<WorkflowTestResponse>(
    "POST",
    `${BASE}/test-node`,
    testData as unknown as Record<string, unknown>,
    { timeout: API_WORKFLOW_TEST_TIMEOUT_MS, headers: KEEPALIVE_HEADERS }
  ).then(throwIfErrorEnvelope);

export const testWorkflow = (testData: WorkflowTestPayload) =>
  apiRequest<WorkflowTestResponse>(
    "POST",
    `${BASE}/test`,
    testData as unknown as Record<string, unknown>,
    { timeout: API_WORKFLOW_TEST_TIMEOUT_MS, headers: KEEPALIVE_HEADERS }
  ).then(throwIfErrorEnvelope);

export const generatePythonTemplate = (schema: any, prompt?: string) =>
  apiRequest<{ template: string }>("POST", `${BASE}/generate-python-template`, {
    parameters_schema: schema,
    prompt,
  } as unknown as Record<string, unknown>);

export interface WorkflowWizardPayload {
  workflow_name: string;
  workflow_json: string;
}

export interface WorkflowWizardResponse {
  id?: string;
  name?: string;
  description?: string;
  user_id?: string;
  agent_id?: string;
  url?: string;
  worflow_json?: string;
  db_record?: Record<string, unknown>;
  [key: string]: unknown;
}

// Create a workflow from onboarding chat
export const createWorkflowFromWizard = (payload: WorkflowWizardPayload) =>
  apiRequest<WorkflowWizardResponse>(
    "POST",
    "workflow-manager/config/from-wizard",
    payload as unknown as Record<string, unknown>
  );

export interface WorkflowBuilderPayload {
  workflow_name: string;
  /** Simplified workflow specification. Either this or conversation_id is required. */
  workflow_json?: string;
  /** Create from the draft the builder agent finalized in this conversation. */
  conversation_id?: string;
  workflow_description?: string;
}

// Create a workflow from the enhanced builder format (supports branching, tool connections, config overrides)
export const createWorkflowFromBuilder = (payload: WorkflowBuilderPayload) =>
  apiRequest<WorkflowWizardResponse>(
    "POST",
    "workflow-builder/config/from-builder",
    payload as unknown as Record<string, unknown>
  );
