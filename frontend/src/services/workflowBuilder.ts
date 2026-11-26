import { apiRequest } from "@/config/api";

const BASE = "workflow-builder";

/** One change the builder agent made to the workflow during a turn. */
export interface BuilderChange {
  op:
    | "add_node"
    | "add_tool"
    | "update_node"
    | "remove_node"
    | "connect"
    | "disconnect";
  summary: string;
  node_ids: string[];
}

export interface BuilderIssue {
  code: string;
  severity: "error" | "warning" | "setup";
  message: string;
  node_id: string | null;
  field: string | null;
  /** True when the problem was on the canvas before the agent changed anything. */
  pre_existing: boolean;
}

/** A question the builder asked with its ask_user tool; the options are shown as buttons. */
export interface BuilderQuestion {
  question: string;
  options: string[];
  /** The option the builder would pick, or null. */
  recommended: string | null;
}

export interface BuilderDraft {
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  status: "draft" | "ready";
  revision: number;
  origin: "new" | "canvas";
  summary: string;
  changes: BuilderChange[];
  issues: BuilderIssue[];
  has_errors: boolean;
  /** Set when the builder ended its turn with a question for the person. */
  question?: BuilderQuestion | null;
}

export interface BuilderCanvasSnapshot {
  nodes: Record<string, unknown>[];
  edges: Record<string, unknown>[];
  selected_node_id?: string | null;
  /** Whether the builder's test runs bypass steps that send or create things. */
  simulate_actions?: boolean;
  /** The person's latest test run on the canvas, so the agent can see it without a pasted log. */
  last_test_run?: {
    inputs: Record<string, unknown>;
    response: unknown;
    error: string | null;
  } | null;
}

/**
 * Hand the canvas (including unsaved changes) to the builder agent as the
 * draft it will edit in this conversation.
 */
export const putBuilderDraft = (
  conversationId: string,
  snapshot: BuilderCanvasSnapshot
) =>
  apiRequest<{ revision: number; node_count: number }>(
    "PUT",
    `${BASE}/drafts/${conversationId}`,
    snapshot as unknown as Record<string, unknown>
  );

/** Read the draft back after the agent's turn. */
export const getBuilderDraft = (conversationId: string) =>
  apiRequest<BuilderDraft>("GET", `${BASE}/drafts/${conversationId}`);

/** One tool a Workflow Builder Tools node can give an agent. */
export interface BuilderTool {
  name: string;
  description: string;
}

/** The builder tool set; the canvas uses it to describe the Workflow Builder Tools node. */
export const getBuilderTools = () =>
  apiRequest<BuilderTool[]>("GET", `${BASE}/tools`);

/** Spend totals from the usage ledger. */
export interface BuilderUsageTotals {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  /** Calls the ledger could not price; their tokens count, their cost does not. */
  unpriced_calls: number;
  test_run_calls: number;
  test_run_cost_usd: number;
}

export interface BuilderUsage {
  /** This conversation, or null when none was given. */
  conversation: BuilderUsageTotals | null;
  /** Every conversation the builder ever had on this tenant. */
  all_time: BuilderUsageTotals;
}

/** What the Workflow Builder has spent, in this conversation and over all of them. */
export const getBuilderUsage = (conversationId?: string | null) =>
  apiRequest<BuilderUsage>(
    "GET",
    conversationId ? `${BASE}/usage?conversation_id=${encodeURIComponent(conversationId)}` : `${BASE}/usage`
  );

/** Validate a workflow graph without saving anything. */
export const validateWorkflowGraph = (snapshot: BuilderCanvasSnapshot) =>
  apiRequest<{ valid: boolean; issues: Omit<BuilderIssue, "pre_existing">[] }>(
    "POST",
    `${BASE}/validate`,
    snapshot as unknown as Record<string, unknown>
  );

export interface BuilderDraftStatus {
  status: "empty" | "draft" | "ready";
  /** Finalized by the agent and free of blocking errors. */
  ready: boolean;
  node_count: number;
  summary: string;
  /** A question the builder asked with ask_user, if its last turn ended with one. */
  question?: BuilderQuestion | null;
  /** The draft in the simplified specification format, for previewing. */
  spec: {
    workflow: {
      uniqueId: string;
      node_name: string;
      function_of_node: string;
      config?: Record<string, unknown>;
    }[];
    edges: { from: string; to: string; sourceHandle?: string; targetHandle?: string }[];
  } | null;
}

/**
 * Draft status for a chat that runs before login (onboarding), where there is
 * no user session yet: it authenticates with the same API key the chat uses.
 */
export const getBuilderDraftStatus = async (
  conversationId: string,
  credentials: { baseUrl: string; apiKey: string; tenant?: string }
): Promise<BuilderDraftStatus | null> => {
  const headers: Record<string, string> = { "x-api-key": credentials.apiKey };
  if (credentials.tenant) headers["x-tenant-id"] = credentials.tenant;
  const response = await fetch(
    `${credentials.baseUrl.replace(/\/$/, "")}/api/${BASE}/drafts/${conversationId}/status`,
    { headers }
  );
  if (!response.ok) return null;
  return (await response.json()) as BuilderDraftStatus;
};

/**
 * The reason a build was rejected, from the builder API's error body
 * (`detail.message` plus the first issue), or null when there is none.
 */
export const builderErrorMessage = (error: unknown): string | null => {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const { message, issues } = detail as {
      message?: string;
      issues?: { message?: string }[];
    };
    const first = issues?.[0]?.message;
    if (message && first) return `${message}: ${first}`;
    return message || first || null;
  }
  return null;
};

// ── Focused AI actions on the canvas (one model call, no builder turn) ──

export type AssistAction =
  | "explain_node"
  | "explain_group"
  | "describe_workflow"
  | "explain_step"
  | "suggest_tests"
  | "review"
  | "improve_prompt"
  | "generate_code"
  | "optimize"
  | "add_step";

/** An approved change is applied with `applyBuilderOperations`; nothing lands until then. */
export interface AssistProposal {
  title: string;
  why: string;
  operations: Record<string, unknown>[];
}

export interface ReviewFinding {
  severity: "error" | "warning" | "setup";
  code: string;
  node_id: string | null;
  message: string;
  /** A message to send the builder to fix it, or null when only the user can. */
  fix: string | null;
}

export type AssistResult =
  | { kind: "text"; text: string }
  | { kind: "messages"; messages: string[] }
  | { kind: "proposals"; proposals: AssistProposal[] }
  | { kind: "review"; findings: ReviewFinding[] };

export const runAssistAction = (
  snapshot: BuilderCanvasSnapshot,
  action: AssistAction,
  nodeIds: string[] = [],
  instruction = "",
  /** For add_step: the output of the first node that the new step follows. */
  sourceHandle?: string
) =>
  apiRequest<AssistResult>(
    "POST",
    `${BASE}/assist`,
    {
      snapshot,
      action,
      node_ids: nodeIds,
      instruction,
      source_handle: sourceHandle ?? null,
    } as unknown as Record<string, unknown>,
    {},
    { rethrowForbidden: true }
  );

/** Apply approved operations to the canvas as sent; returns the updated draft payload. */
export const applyBuilderOperations = (
  snapshot: BuilderCanvasSnapshot,
  operations: Record<string, unknown>[]
) =>
  apiRequest<BuilderDraft & { report: string }>(
    "POST",
    `${BASE}/assist/apply`,
    { snapshot, operations } as unknown as Record<string, unknown>,
    {},
    { rethrowForbidden: true }
  );
