import { apiRequest, API_WORKFLOW_TEST_TIMEOUT_MS } from "@/config/api";
import { FieldSchema } from "@/interfaces/dynamicFormSchemas.interface";

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
  status: string;
  input: string;
  output: string;
  /** True when one or more nodes failed even though the run completed. */
  has_failures?: boolean;
  /** Details of the nodes that failed, if any. */
  failed_nodes?: FailedNode[];
  token_usage?: WorkflowTokenUsage;
  [key: string]: any;
}

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

export type TrainingJobStatus = "queued" | "running" | "succeeded" | "failed";

export interface TrainingJobProgress {
  stage: string;
  message: string;
  percent: number;
  elapsed_seconds?: number;
}

/** A test run that trains a model runs on the background ML worker as a job. */
export interface TrainingJob {
  job_id: string;
  kind: "workflow" | "node";
  status: TrainingJobStatus;
  progress: TrainingJobProgress;
  result: WorkflowTestResponse | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestRunOptions {
  /** Called with every status update while a training job runs. */
  onTrainingProgress?: (job: TrainingJob) => void;
}

export const TRAINING_JOB_POLL_INTERVAL_MS = 2000;
// Consecutive failed status checks (e.g. a network blip) tolerated before giving up.
const TRAINING_JOB_MAX_POLL_ERRORS = 3;
// A job can wait up to 2h10m for a worker and then train for up to 2h before
// the server reports it failed; stop waiting a little after that in any case.
export const TRAINING_JOB_MAX_WAIT_MS = (4 * 60 + 30) * 60 * 1000;

export const isTrainingJob = (value: unknown): value is TrainingJob =>
  !!value &&
  typeof value === "object" &&
  typeof (value as TrainingJob).job_id === "string" &&
  typeof (value as TrainingJob).status === "string" &&
  !!(value as TrainingJob).progress;

export const getTrainingJob = (jobId: string) =>
  apiRequest<TrainingJob>("GET", `${BASE}/test-jobs/${encodeURIComponent(jobId)}`);

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** Poll a training job until it finishes; resolves with the test result or throws its error. */
export const waitForTrainingJob = async (
  job: TrainingJob,
  onProgress?: (job: TrainingJob) => void,
  pollIntervalMs: number = TRAINING_JOB_POLL_INTERVAL_MS,
  maxWaitMs: number = TRAINING_JOB_MAX_WAIT_MS
): Promise<WorkflowTestResponse | null> => {
  const deadline = Date.now() + maxWaitMs;
  let current = job;
  let pollErrors = 0;
  for (;;) {
    onProgress?.(current);
    if (current.status === "succeeded") return current.result;
    if (current.status === "failed") throw new Error(current.error || "Training failed");
    if (Date.now() >= deadline) {
      throw new Error("Stopped waiting for the training job. It took longer than the training time limit.");
    }

    await delay(pollIntervalMs);
    try {
      const next = await getTrainingJob(current.job_id);
      if (!next) throw new Error("The training job could not be read");
      current = next;
      pollErrors = 0;
    } catch (error) {
      pollErrors += 1;
      if (pollErrors >= TRAINING_JOB_MAX_POLL_ERRORS) throw error;
    }
  }
};

const runTest = async (
  endpoint: string,
  testData: NodeTestPayload | WorkflowTestPayload,
  options?: TestRunOptions
): Promise<WorkflowTestResponse | null> => {
  const response = await apiRequest<WorkflowTestResponse | TrainingJob>(
    "POST",
    endpoint,
    testData as unknown as Record<string, unknown>,
    { timeout: API_WORKFLOW_TEST_TIMEOUT_MS }
  );
  return isTrainingJob(response)
    ? waitForTrainingJob(response, options?.onTrainingProgress)
    : response;
};

export const testNode = (testData: NodeTestPayload, options?: TestRunOptions) =>
  runTest(`${BASE}/test-node`, testData, options);

export const testWorkflow = (testData: WorkflowTestPayload, options?: TestRunOptions) =>
  runTest(`${BASE}/test`, testData, options);

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
  workflow_json: string;
  workflow_description?: string;
}

// Create a workflow from the enhanced builder format (supports branching, tool connections, config overrides)
export const createWorkflowFromBuilder = (payload: WorkflowBuilderPayload) =>
  apiRequest<WorkflowWizardResponse>(
    "POST",
    "workflow-builder/config/from-builder",
    payload as unknown as Record<string, unknown>
  );
