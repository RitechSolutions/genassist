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

// What a rule is graded over: each turn, one targeted turn, or the whole
// conversation ("at least once during it").
export type RuleScope = "specific_turn" | "every_turn" | "conversation";

// Every rule-based technique (tool usage, route, action) carries these.
export interface RuleScopeTarget {
  scope: RuleScope;
  target_source_conversation_id?: string | null;
  // A specific-turn rule may name several turns; it is graded once per turn.
  target_case_ids?: string[];
  target_turn_indexes?: number[];
  // The single-turn shape saved before that, still read when editing.
  target_case_id?: string | null;
  target_turn_index?: number | null;
}

// An imported multi-turn conversation available for specific-turn targeting.
export interface RuleConversation {
  id: string; // source_conversation_id
  label: string;
  turns: { caseId: string; turnIndex: number; label: string }[];
}

// ---- Route / Action multi-rule builder drafts ----

export interface RouteRuleDraft extends RuleScopeTarget {
  id: string;
  router: string;
  expected: string;
}

export interface ActionRuleDraft extends RuleScopeTarget {
  id: string;
  node: string;
  nodeType: string;
  shouldFire: boolean;
}

export type JudgeRuleSource =
  | "expected_output"
  | "kb_retrievals"
  | "conversation_context"
  | "tool_events"
  | "none"
  | "legacy";

export interface JudgeRuleDraft {
  label: string;
  rubric: string;
  minScore: string;
  sourceType: JudgeRuleSource;
  sourceField: string;
}

// Extra per-tool assertions (result/argument checks). Not edited in the builder yet,
// but preserved verbatim so editing a rule never drops them.
export interface ToolUsagePerToolCheck {
  result_not_empty?: boolean;
  result_contains?: string | null;
  expected_args?: Record<string, unknown> | null;
}

export interface ToolUsageRule extends RuleScopeTarget {
  id: string;
  agent_id?: string | null;
  tool_ids: string[];
  operator: ToolUsageOperator;
  require_success?: boolean;
  min_calls?: number | null;
  max_calls?: number | null;
  per_tool?: Record<string, ToolUsagePerToolCheck>;
}

// Techniques graded per scope, stored as one result row per rule check.
export type RuleTechnique = "tool_used" | "route_taken" | "action_taken";

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
  // Route / Action results describe one node and what it did.
  router?: { id: string | null; label: string | null };
  node?: { id: string | null; label: string | null };
  expected?: string;
  observed?: string;
  show_comment_on_pass?: boolean;
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
  technique: RuleTechnique;
  rule_id: string;
  scope: string;
  case_id?: string | null;
  source_conversation_id?: string | null;
  status: "passed" | "failed" | "not_evaluated";
  score?: number | null;
  details?: Record<string, unknown> | null;
  created_at: string;
}

