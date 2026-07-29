export interface TestEvaluationConfig {
  id: string;
  name: string;
  description?: string;
  suite_id: string;
  workflow_id?: string;
  techniques: string[];
  technique_configs?: Record<string, Record<string, unknown>>;
  input_metadata?: Record<string, unknown>;
  run_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface StartedEvaluationRun {
  evaluation_id: string;
  run_id?: string;
  suite_id?: string;
  status: string;
  error?: string;
}

export interface WorkflowEvaluationSummary {
  workflow_id: string | null;
  eval_count: number;
  health: number | null;
  finished_count: number;
  any_running: boolean;
}

export interface PaginatedEvaluations {
  items: TestEvaluationConfig[];
  total: number;
  total_unfiltered: number;
  page: number;
  page_size: number;
  any_running: boolean;
}

// ---- Tool Usage catalogue + rules ----

export interface EvaluationToolInfo {
  id: string;
  name: string;
  label: string;
  type: string;
}

export interface EvaluationAgentInfo {
  id: string;
  label: string;
  type: string;
  workflow_path: string[];
  tools: EvaluationToolInfo[];
}

export interface EvaluationRouterBranch {
  value: string;
  destination: string | null;
}

export interface EvaluationRouterInfo {
  id: string;
  label: string;
  workflow_path: string[];
  branches: EvaluationRouterBranch[];
}

export interface EvaluationActionNodeInfo {
  id: string;
  label: string;
  type: string;
  workflow_path: string[];
}

export interface EvaluationToolCatalog {
  workflow_id: string;
  agents: EvaluationAgentInfo[];
  routers: EvaluationRouterInfo[];
  action_nodes: EvaluationActionNodeInfo[];
}

export type ToolUsageOperator = "all" | "any" | "none" | "only";
export type ToolUsageScope = "specific_turn" | "every_turn" | "conversation";

// Extra per-tool assertions (result/argument checks). Not edited in the builder yet,
// but preserved verbatim so editing a rule never drops them.
export interface ToolUsagePerToolCheck {
  result_not_empty?: boolean;
  result_contains?: string | null;
  expected_args?: Record<string, unknown> | null;
}

export interface ToolUsageRule {
  id: string;
  agent_id?: string | null;
  tool_ids: string[];
  operator: ToolUsageOperator;
  require_success?: boolean;
  scope: ToolUsageScope;
  target_case_id?: string | null;
  target_source_conversation_id?: string | null;
  target_turn_index?: number | null;
  min_calls?: number | null;
  max_calls?: number | null;
  per_tool?: Record<string, ToolUsagePerToolCheck>;
}

// The readable, rename-proof snapshot the backend stores with each result.
export interface ToolRuleTargetInfo {
  type: "conversation" | "turn";
  label: string;
  turn_count?: number;
}

export interface ToolRuleResultDetails {
  rule_number?: number;
  rule_summary?: string;
  agent?: { id: string | null; label: string };
  tools?: Record<string, { label: string }>;
  target?: ToolRuleTargetInfo;
  observed_tools?: string[];
  missing_tools?: string[];
  failed_tools?: string[];
  forbidden_tools?: string[];
  check_failures?: Record<string, string>;
  call_counts?: Record<string, number>;
  successful_call_counts?: Record<string, number>;
  comment?: string;
  turn_index?: number | null;
  operator?: string;
  rule?: {
    tool_ids?: string[];
    operator?: string;
    require_success?: boolean;
    min_calls?: number | null;
    max_calls?: number | null;
  };
}

export interface TestToolRuleResult {
  id: string;
  run_id: string;
  rule_id: string;
  scope: string;
  case_id?: string | null;
  source_conversation_id?: string | null;
  status: "passed" | "failed" | "not_evaluated";
  score?: number | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

