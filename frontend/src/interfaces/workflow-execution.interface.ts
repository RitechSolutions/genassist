import { WorkflowTestResponse } from "@/services/workflows";

/**
 * @deprecated Legacy shape that does not match the live test-response wire format. Not used to
 * parse the Execution view; see `ExecutionViewModel` and `buildExecutionViewModel`. (Note there
 * is a separate, actively-used `WorkflowExecutionState` in the Workflows context — unrelated.)
 */
// Extended execution state that includes real-time tracking
export interface WorkflowExecutionState extends Omit<WorkflowTestResponse, 'execution_summary'> {
  execution_summary: {
    execution_id: string;
    thread_id: string;
    timestamp: string;
    execution_path: string[];
    input: string;
    node_outputs: Record<string, unknown>;
  };
  // Current execution status
  isExecuting: boolean;
  currentStep: number;
  totalSteps: number;
  
  // Real-time execution tracking
  executionStartTime: number;
  executionEndTime?: number;
  
  // Node execution details
  nodeExecutionStatus: Record<string, NodeExecutionStatus>;
  
  // Execution history for debugging
  executionHistory: ExecutionStep[];
  
  // Error handling
  errors: ExecutionError[];
  
  // Performance metrics
  performanceMetrics: PerformanceMetrics;
}

/**
 * @deprecated Does NOT match the backend wire format. The actual per-node payload in
 * `state.nodeExecutionStatus` uses `type/name/status("running"|"success"|"failed")/startTime/
 * endTime/time_taken/input/output/error` (node id is the map key) — see `RawNodeExecutionEntry`
 * and the `buildExecutionViewModel` adapter. Do not parse the test response through this type.
 */
// Status of individual node execution
export interface NodeExecutionStatus {
  nodeId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  startTime?: number;
  endTime?: number;
  duration?: number;
  input?: Record<string, any>;
  output?: Record<string, any>;
  error?: string;
  retryCount: number;
  maxRetries: number;
}

// Individual execution step for history tracking
export interface ExecutionStep {
  stepNumber: number;
  nodeId: string;
  nodeType: string;
  nodeName: string;
  timestamp: number;
  input: Record<string, any>;
  output: Record<string, any>;
  status: 'success' | 'error' | 'skipped';
  duration: number;
  metadata?: Record<string, any>;
}

// Error information for failed executions
export interface ExecutionError {
  nodeId: string;
  nodeType: string;
  error: string;
  timestamp: number;
  retryCount: number;
  context?: Record<string, any>;
}

/**
 * @deprecated Backend `performanceMetrics` is NOT recomputed on failed runs (only on
 * `complete_execution`), so it is stale/zeroed when a workflow fails. The Execution view
 * derives counts/slowest-node/duration from raw per-node timings instead. Prefer
 * `ExecutionViewModel`.
 */
// Performance metrics for the workflow execution
export interface PerformanceMetrics {
  totalExecutionTime: number;
  averageNodeExecutionTime: number;
  slowestNode: string;
  slowestNodeTime: number;
  fastestNode: string;
  fastestNodeTime: number;
  totalNodesExecuted: number;
  successRate: number;
}

// Actions that can be performed on the execution state
export interface WorkflowExecutionActions {
  // Start a new execution
  startExecution: (input: Record<string, unknown>) => void;
  
  // Stop current execution
  stopExecution: () => void;
  
  // Update node output
  updateNodeOutput: (nodeId: string, output: Record<string, unknown>) => void;
  
  // Mark node as completed
  markNodeCompleted: (nodeId: string, output: Record<string, unknown>, nodeType: string, nodeName: string) => void;
  
  // Mark node as failed
  markNodeFailed: (nodeId: string, error: string, nodeType: string, nodeName: string) => void;
  
  // Retry failed node
  retryNode: (nodeId: string) => void;
  
  // Get node output
  getNodeOutput: (nodeId: string) => Record<string, unknown> | undefined;
  
  // Get all available outputs for a node
  getAvailableOutputs: (nodeId: string) => Record<string, unknown>;
  
  // Clear execution state
  clearExecution: () => void;
  
  // Export execution state
  exportExecutionState: () => WorkflowExecutionState;
}

// Context type for the workflow execution
export interface WorkflowExecutionContextType {
  state: WorkflowExecutionState | null;
  actions: WorkflowExecutionActions;
  isLoading: boolean;
  error: string | null;
}

// ── Node Execution Visualization ("Execution" tab) ──────────────────────────
// Types below reflect the ACTUAL workflow-test wire format and the normalized,
// display-ready model the Execution view renders. See `utils/executionView.ts`.

/** Raw per-node status values emitted by the backend. */
export type RawNodeExecutionStatus = "running" | "success" | "failed";

/**
 * The real per-node payload found in `response.state.nodeExecutionStatus` (keyed by node id).
 * Every field is optional because entries are built incrementally and older runs may be
 * archived/partial. This is the shape the adapter narrows from `unknown`.
 */
export interface RawNodeExecutionEntry {
  type?: string;
  name?: string;
  status?: RawNodeExecutionStatus;
  startTime?: number;
  endTime?: number;
  time_taken?: number;
  input?: unknown;
  output?: unknown;
  error?: string | null;
}

/** What a node asked of prompt caching, and what it got. */
export interface RawPromptCachingDiagnostic {
  requested?: boolean;
  applied?: boolean;
  /** Provider-reported cache activity, stamped after the call */
  cache_read_tokens?: number;
  cache_creation_tokens?: number;
}

export interface PromptCachingDiagnostic {
  requested: boolean;
  applied: boolean;
  cacheReadTokens?: number;
  cacheCreationTokens?: number;
}

/** Normalized, display-ready status used by the Execution view. */
export type ExecutionNodeStatus =
  | "completed"
  | "failed"
  | "running"
  | "skipped"
  | "pending";

/** A single node as shown in the Execution view (graph, summary, detail panel). */
export interface NodeExecutionView {
  nodeId: string;
  name: string;
  type?: string;
  status: ExecutionNodeStatus;
  startTime?: number;
  endTime?: number;
  durationMs?: number;
  input?: unknown;
  output?: unknown;
  error?: string | null;
  /** 0-based execution order, when derivable from startTime. */
  order?: number;
  promptCaching?: PromptCachingDiagnostic;
}

/** Everything the Execution view needs, derived once from the test response. */
export interface ExecutionViewModel {
  nodes: NodeExecutionView[];
  /** O(1) status lookup by node id (for overlaying the DAG). */
  byId: Record<string, NodeExecutionView>;
  counts: Record<ExecutionNodeStatus, number>;
  totalNodes: number;
  totalSteps?: number;
  currentStep?: number;
  executionStartTime?: number;
  executionEndTime?: number;
  /** Overall wall-clock duration in ms, when derivable. */
  overallDurationMs?: number;
  /** Node id with the largest duration, when any node has a duration. */
  slowestNodeId?: string;
  /**
   * Prompt-caching diagnostics keyed by node id. Sub-agent children appear here too,
   * though they are absent from `nodes`/`byId` — the parent run did not execute them.
   */
  promptCachingDiagnostics: Record<string, PromptCachingDiagnostic>;
}

/** Which of the four interactive states the Execution view should render. */
export type ExecutionViewState = "loading" | "error" | "empty" | "data";
