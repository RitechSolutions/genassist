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
  /** Calls made by workflows the Workflow Builder test-ran inside this run; included in
   *  the totals above and summed here so the builder's own cost can be told apart. */
  test_runs?: {
    calls: number;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
  };
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
  // The canvas node's id. A Train Model node is tested under it so a retest
  // updates the model the previous test registered instead of colliding with it.
  node_id?: string;
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

export type TrainingJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

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
  /** Set by the client: the user already had this job running, so the new test followed it instead. */
  reattached?: boolean;
}

export interface TestRunOptions {
  /** Called with every status update while a training job runs. */
  onTrainingProgress?: (job: TrainingJob) => void;
  /** Stops waiting for a training job (e.g. the dialog closed). The job itself keeps running. */
  signal?: AbortSignal;
}

export const TRAINING_JOB_POLL_INTERVAL_MS = 2000;
// Consecutive failed status checks (e.g. a network blip) tolerated before giving up.
const TRAINING_JOB_MAX_POLL_ERRORS = 3;
// A job can wait up to 2h10m for a worker and then train for up to 2h before
// the server reports it failed; stop waiting a little after that in any case.
export const TRAINING_JOB_MAX_WAIT_MS = (4 * 60 + 30) * 60 * 1000;
const TRAINING_JOB_ALREADY_RUNNING = "ML_TRAINING_JOB_ALREADY_RUNNING";

/** Thrown when waiting for a training job stops because its AbortSignal fired. */
export class TrainingWaitAbortedError extends Error {
  constructor() {
    super("Stopped waiting for the training job");
    this.name = "TrainingWaitAbortedError";
  }
}

export const isTrainingWaitAborted = (error: unknown): boolean => error instanceof TrainingWaitAbortedError;

export const isTrainingJob = (value: unknown): value is TrainingJob =>
  !!value &&
  typeof value === "object" &&
  typeof (value as TrainingJob).job_id === "string" &&
  typeof (value as TrainingJob).status === "string" &&
  !!(value as TrainingJob).progress;

export const getTrainingJob = (jobId: string) =>
  apiRequest<TrainingJob>("GET", `${BASE}/test-jobs/${encodeURIComponent(jobId)}`);

/** The user's queued or running training test, if any. */
export const getActiveTrainingJob = () => apiRequest<TrainingJob>("GET", `${BASE}/test-jobs/active`);

/** Cancel a queued or running training test; resolves with the job as it now is. */
export const cancelTrainingJob = (jobId: string) =>
  apiRequest<TrainingJob>("POST", `${BASE}/test-jobs/${encodeURIComponent(jobId)}/cancel`);

const delay = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new TrainingWaitAbortedError());
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(new TrainingWaitAbortedError());
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });

/** Poll a training job until it finishes; resolves with the test result or throws its error. */
export const waitForTrainingJob = async (
  job: TrainingJob,
  onProgress?: (job: TrainingJob) => void,
  pollIntervalMs: number = TRAINING_JOB_POLL_INTERVAL_MS,
  maxWaitMs: number = TRAINING_JOB_MAX_WAIT_MS,
  signal?: AbortSignal
): Promise<WorkflowTestResponse | null> => {
  const deadline = Date.now() + maxWaitMs;
  let current = job;
  let pollErrors = 0;
  for (;;) {
    if (signal?.aborted) throw new TrainingWaitAbortedError();
    onProgress?.(current);
    if (current.status === "succeeded") return current.result;
    if (current.status === "failed") {
      // A run whose node failed comes back with its response, which shows
      // the failed node like any failed test run (TM-17). The job's status
      // wins: a run that still answered failed as a training test.
      if (current.result) return { ...current.result, status: "failed" };
      throw new Error(current.error || "Training failed");
    }
    if (current.status === "cancelled") throw new Error(current.error || "The training test was cancelled.");
    if (Date.now() >= deadline) {
      throw new Error("Stopped waiting for the training job. It took longer than the training time limit.");
    }

    await delay(pollIntervalMs, signal);
    try {
      const next = await getTrainingJob(current.job_id);
      if (!next) throw new Error("The training job could not be read");
      current = job.reattached ? { ...next, reattached: true } : next;
      pollErrors = 0;
    } catch (error) {
      pollErrors += 1;
      if (pollErrors >= TRAINING_JOB_MAX_POLL_ERRORS) throw error;
    }
  }
};

type ErrorResponse = { response?: { status?: number; data?: { error_key?: string; error_detail?: unknown; detail?: unknown } } };

const isAlreadyRunningError = (error: unknown): boolean => {
  const response = (error as ErrorResponse)?.response;
  return response?.status === 409 && response.data?.error_key === TRAINING_JOB_ALREADY_RUNNING;
};

/** The server's own explanation of a refused test (AppException error_detail, or FastAPI detail). */
const serverMessage = (error: unknown): string | null => {
  const data = (error as ErrorResponse)?.response?.data;
  const message = data?.error_detail ?? data?.detail;
  return typeof message === "string" && message.trim() ? message : null;
};

const startTest = async (
  endpoint: string,
  testData: NodeTestPayload | WorkflowTestPayload
): Promise<WorkflowTestResponse | TrainingJob | null> => {
  try {
    // Kept alive while the test runs; an error then arrives as an error
    // envelope in the body, which throwIfErrorEnvelope throws as the same
    // { response: { status, data } } error the checks below read.
    return await apiRequest<WorkflowTestResponse | TrainingJob>(
      "POST",
      endpoint,
      testData as unknown as Record<string, unknown>,
      { timeout: API_WORKFLOW_TEST_TIMEOUT_MS, headers: KEEPALIVE_HEADERS },
      // A 403 here explains itself (e.g. a training test needs a signed-in user).
      { rethrowForbidden: true }
    ).then(throwIfErrorEnvelope);
  } catch (error) {
    if (isAlreadyRunningError(error)) {
      // The user's earlier training test is still running (e.g. they closed the
      // dialog): follow it, so they can see it finish or cancel it.
      const active = await getActiveTrainingJob().catch(() => null);
      if (active) return { ...active, reattached: true };
    }
    // e.g. an oversized hyperparameter search: show why, not "status code 400".
    const message = serverMessage(error);
    throw message ? Object.assign(new Error(message), { cause: error }) : error;
  }
};

const REATTACHED_OUTCOME: Record<TrainingJobStatus, string> = {
  queued: "is still queued",
  running: "is still running",
  succeeded: "has finished",
  failed: "has failed",
  cancelled: "was cancelled",
};

/**
 * Follow the user's earlier training test to its end, then tell them to run
 * this one again. Its result belongs to another node or workflow (or to an
 * older configuration), so it is never returned as this test's result.
 */
const followEarlierJob = async (job: TrainingJob, options?: TestRunOptions): Promise<never> => {
  let outcome: TrainingJobStatus = job.status;
  try {
    await waitForTrainingJob(
      job,
      (update) => {
        outcome = update.status;
        options?.onTrainingProgress?.(update);
      },
      TRAINING_JOB_POLL_INTERVAL_MS,
      TRAINING_JOB_MAX_WAIT_MS,
      options?.signal
    );
  } catch (error) {
    if (isTrainingWaitAborted(error)) throw error;
  }
  throw new Error(
    `Your earlier training test ${REATTACHED_OUTCOME[outcome]}. Run the test again to test this configuration.`
  );
};

const runTest = async (
  endpoint: string,
  testData: NodeTestPayload | WorkflowTestPayload,
  options?: TestRunOptions
): Promise<WorkflowTestResponse | null> => {
  const response = await startTest(endpoint, testData);
  if (!isTrainingJob(response)) return response;
  if (response.reattached) return followEarlierJob(response, options);
  return waitForTrainingJob(
    response,
    options?.onTrainingProgress,
    TRAINING_JOB_POLL_INTERVAL_MS,
    TRAINING_JOB_MAX_WAIT_MS,
    options?.signal
  );
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
