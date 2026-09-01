import {
  ExecutionNodeStatus,
  ExecutionViewModel,
  ExecutionViewState,
  NodeExecutionView,
  PromptCachingDiagnostic,
  RawNodeExecutionEntry,
} from '@/interfaces/workflow-execution.interface';
import { Workflow } from '@/interfaces/workflow.interface';

/**
 * Pure adapters that turn the loosely-typed workflow-test response into the normalized model
 * the "Execution" view renders. Kept side-effect-free and defensive so they can be unit-tested
 * and never throw on partial/malformed payloads (see spec FR-8 / AC-7).
 *
 * Wire-format notes (verified against the backend `WorkflowState.get_full_state`):
 *  - run-level fields + `nodeExecutionStatus` live under `response.state` (not top-level).
 *  - per-node status is `"running" | "success" | "failed"` (NOT `"completed"`), duration is
 *    `time_taken` (ms), and the node id is the map key.
 *  - failed runs leave `performanceMetrics` stale, so we recompute everything from raw timings.
 *  - re-run nodes are archived under `"{id}_0"`, `"{id}_1"`, … which we collapse to the latest
 *    (un-suffixed) entry.
 */

const EMPTY_COUNTS: Record<ExecutionNodeStatus, number> = {
  completed: 0,
  failed: 0,
  running: 0,
  skipped: 0,
  pending: 0,
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const asNumber = (value: unknown): number | undefined =>
  typeof value === 'number' && Number.isFinite(value) ? value : undefined;

const asString = (value: unknown): string | undefined => (typeof value === 'string' ? value : undefined);

/** Map the backend status to the normalized, display-ready status. */
const normalizeStatus = (raw: unknown): ExecutionNodeStatus => {
  switch (raw) {
    case 'success':
      return 'completed';
    case 'failed':
      return 'failed';
    case 'running':
      return 'running';
    case 'skipped':
      return 'skipped';
    default:
      return 'pending';
  }
};

/**
 * Return the object that actually holds the run-level fields + `nodeExecutionStatus`.
 * Prefer `response.state` (where the backend nests them); fall back to the top level.
 */
const resolveStateBag = (response: unknown): Record<string, unknown> => {
  if (!isRecord(response)) return {};
  const state = response.state;
  if (isRecord(state) && isRecord(state.nodeExecutionStatus)) return state;
  if (isRecord(response.nodeExecutionStatus)) return response;
  // Neither location has the map; still return `state` if present so run-level fields resolve.
  return isRecord(state) ? state : response;
};

/**
 * A key is an archived earlier run only when it ends in `_<digit>+` AND its base id also
 * exists in the same map — this avoids misclassifying legitimate ids like `r2_destmissing`
 * or a lone `step_0`.
 */
const isArchivedKey = (key: string, keys: Set<string>): boolean => {
  const match = key.match(/^(.+)_(\d+)$/);
  return Boolean(match && keys.has(match[1]));
};

/** Collapse archived re-run keys (`"{id}_N"`) to the latest entry. */
const stripArchivedKeys = (map: Record<string, unknown>): Record<string, RawNodeExecutionEntry> => {
  const keys = Object.keys(map);
  const keySet = new Set(keys);
  const result: Record<string, RawNodeExecutionEntry> = {};
  for (const key of keys) {
    if (isArchivedKey(key, keySet)) continue;
    const entry = map[key];
    result[key] = isRecord(entry) ? (entry as RawNodeExecutionEntry) : {};
  }
  return result;
};

const normalizePromptCaching = (value: unknown): PromptCachingDiagnostic | undefined => {
  if (!isRecord(value)) return undefined;
  if (typeof value.requested !== 'boolean' || typeof value.applied !== 'boolean') return undefined;
  const cacheReadTokens = asNumber(value.cache_read_tokens);
  const cacheCreationTokens = asNumber(value.cache_creation_tokens);
  return {
    requested: value.requested,
    applied: value.applied,
    ...(cacheReadTokens !== undefined ? { cacheReadTokens } : {}),
    ...(cacheCreationTokens !== undefined ? { cacheCreationTokens } : {}),
  };
};

const deriveDuration = (entry: RawNodeExecutionEntry): number | undefined => {
  const taken = asNumber(entry.time_taken);
  if (taken !== undefined) return taken;
  const start = asNumber(entry.startTime);
  const end = asNumber(entry.endTime);
  if (start !== undefined && end !== undefined && end >= start) return end - start;
  return undefined;
};

/**
 * Build the normalized Execution view model from a raw workflow-test `response`. Accepts
 * `unknown` (not the `any`-indexed `WorkflowTestResponse`) so every access is type-checked, and
 * never throws — malformed input yields an empty model.
 */
export const buildExecutionViewModel = (response: unknown, workflow?: Workflow | null): ExecutionViewModel => {
  const bag = resolveStateBag(response);
  const rawMap = isRecord(bag.nodeExecutionStatus) ? bag.nodeExecutionStatus : {};
  const entries = stripArchivedKeys(rawMap);

  // Fallback name lookup from the workflow structure (backend usually includes `name`).
  const nameById = new Map<string, string>();
  for (const node of workflow?.nodes ?? []) {
    const data = node.data as { name?: string } | undefined;
    if (node.id && data?.name) nameById.set(node.id, data.name);
  }

  const rawDiagnostics = isRecord(bag.promptCachingDiagnostics) ? bag.promptCachingDiagnostics : {};

  const nodes: NodeExecutionView[] = Object.entries(entries).map(([nodeId, entry]) => ({
    nodeId,
    name: asString(entry.name) ?? nameById.get(nodeId) ?? nodeId,
    type: asString(entry.type),
    status: normalizeStatus(entry.status),
    startTime: asNumber(entry.startTime),
    endTime: asNumber(entry.endTime),
    durationMs: deriveDuration(entry),
    input: entry.input,
    output: entry.output,
    error: asString(entry.error) ?? null,
    promptCaching: normalizePromptCaching(rawDiagnostics[nodeId]),
  }));

  // Execution order by startTime (nodes without a startTime sort last, stable by id).
  const ordered = [...nodes].sort((a, b) => {
    const sa = a.startTime ?? Number.POSITIVE_INFINITY;
    const sb = b.startTime ?? Number.POSITIVE_INFINITY;
    if (sa !== sb) return sa - sb;
    return a.nodeId.localeCompare(b.nodeId);
  });
  ordered.forEach((node, index) => {
    node.order = index;
  });

  const counts: Record<ExecutionNodeStatus, number> = { ...EMPTY_COUNTS };
  const byId: Record<string, NodeExecutionView> = {};
  let slowestNodeId: string | undefined;
  let slowestDuration = -1;
  for (const node of nodes) {
    counts[node.status] += 1;
    byId[node.nodeId] = node;
    if (node.durationMs !== undefined && node.durationMs > slowestDuration) {
      slowestDuration = node.durationMs;
      slowestNodeId = node.nodeId;
    }
  }

  // Diagnostics ride their own key, so no node count or status derives from them.
  const promptCachingDiagnostics: Record<string, PromptCachingDiagnostic> = {};
  for (const [nodeId, raw] of Object.entries(rawDiagnostics)) {
    const diagnostic = normalizePromptCaching(raw);
    if (diagnostic) promptCachingDiagnostics[nodeId] = diagnostic;
  }

  const executionStartTime = asNumber(bag.execution_start_time);
  const executionEndTime = asNumber(bag.execution_end_time);
  let overallDurationMs: number | undefined;
  if (executionStartTime !== undefined && executionEndTime !== undefined && executionEndTime >= executionStartTime) {
    overallDurationMs = executionEndTime - executionStartTime;
  } else {
    // Fall back to span of per-node timings.
    const starts = nodes.map((n) => n.startTime).filter((n): n is number => n !== undefined);
    const ends = nodes.map((n) => n.endTime).filter((n): n is number => n !== undefined);
    if (starts.length && ends.length) {
      const span = Math.max(...ends) - Math.min(...starts);
      if (span >= 0) overallDurationMs = span;
    }
  }

  return {
    nodes: ordered,
    byId,
    counts,
    totalNodes: nodes.length,
    totalSteps: asNumber(bag.total_steps),
    currentStep: asNumber(bag.current_step),
    executionStartTime,
    executionEndTime,
    overallDurationMs,
    slowestNodeId,
    promptCachingDiagnostics,
  };
};

/**
 * Decide which of the four interactive states the Execution view should render. Pure so the
 * empty/loading/error/data decision is unit-testable without a DOM.
 */
export const deriveExecutionViewState = (response: unknown, testing: boolean, error: unknown): ExecutionViewState => {
  if (testing) return 'loading';
  if (error) return 'error';
  if (response === null || response === undefined) return 'empty';
  return 'data';
};

/** Human-readable duration (ms) → e.g. "12 ms", "1.34 s", "2 m 03 s". */
export const formatDuration = (ms?: number): string => {
  if (ms === undefined || !Number.isFinite(ms) || ms < 0) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(2)} s`;
  const minutes = Math.floor(seconds / 60);
  const rem = Math.round(seconds % 60);
  return `${minutes} m ${String(rem).padStart(2, '0')} s`;
};
