export interface TestEvaluationConfig {
  id: string;
  name: string;
  description?: string;
  /** A team's own label, shared with datasets; null when none is set, and "" clears it on an update. */
  category?: string | null;
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
  /** Display name when the value is opaque (a Switch case id). */
  label?: string | null;
}

export interface EvaluationRouterInfo {
  id: string;
  label: string;
  /** routerNode or switchNode. */
  type?: string | null;
  workflow_path: string[];
  branches: EvaluationRouterBranch[];
}

export interface EvaluationActionNodeInfo {
  id: string;
  label: string;
  type: string;
  workflow_path: string[];
}

// A value the workflow remembers between turns: a stateful Chat Input field or a Set State key.
export interface EvaluationStateKeyInfo {
  key: string;
  source: "chat_input" | "set_state" | string;
  node_label: string;
  workflow_path: string[];
}

export interface EvaluationToolCatalog {
  workflow_id: string;
  agents: EvaluationAgentInfo[];
  routers: EvaluationRouterInfo[];
  action_nodes: EvaluationActionNodeInfo[];
  state_keys?: EvaluationStateKeyInfo[];
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
export type RuleTechnique = "tool_used" | "route_taken" | "action_taken" | "checks";

// ---- Should / Should not checks ----

export type CheckKind =
  | "reply_mentions"
  | "reply_matches"
  | "reply_meets"
  | "reply_grounded"
  | "tool_called"
  | "only_tools"
  | "step_runs"
  | "step_fails"
  | "route_taken"
  | "state_equals"
  | "value_equals";
// How closely a reply has to match the dataset's expected reply.
export type CheckMatch = "exact" | "contains" | "meaning";
// What an AI grader reads besides the reply; for reply_grounded, what the reply sticks to.
export type CheckContext = "expected_reply" | "knowledge_base" | "tool_calls" | "session" | "run_value";

// One more tool a check is about; as another tool that should be called, with its own values and result.
export interface CheckToolRef {
  tool?: string | null;
  tool_name?: string | null;
  args?: Record<string, string>;
  result_not_empty?: boolean;
  result_contains?: string | null;
  // The form's value rows as typed, never saved.
  rows?: [string, string][];
}
export type CheckLevel = "every_conversation" | "conversation" | "turn";
export type CheckExpect = "should" | "should_not";
// Every conversation only: hold on every turn, or at some point.
export type CheckWhen = "every_turn" | "anywhere";

// One expectation about a conversation. Names travel with ids so a check survives a copied workflow.
/** What grades a reply against its source besides the AI grader, as NLI and Provenance did. */
export type CheckGrader = "nli" | "similarity";

export interface ScenarioCheck {
  id: string;
  expect: CheckExpect;
  kind: CheckKind;
  level: CheckLevel;
  when: CheckWhen;
  /** The conversation level's chosen conversations. */
  conversation_ids?: string[] | null;
  /** A turn's conversation; one chosen conversation was stored here before several could be. */
  conversation_id?: string | null;
  case_id?: string | null;
  turn_index?: number | null;
  turn_message?: string | null;
  text?: string | null;
  rubric?: string | null;
  context?: CheckContext | null;
  context_path?: string | null;
  /** An AI-graded check passes at this score; 0.5 when not set. */
  pass_score?: number | null;
  /** An AI-graded check's own grader; the evaluation's when not set. */
  llm_provider_id?: string | null;
  /** reply_grounded: the NLI model or text similarity in place of the AI grader. */
  grader?: CheckGrader | null;
  nli_model?: string | null;
  fail_on_contradiction?: boolean;
  /** Text similarity's embedding model: type, model_name, base_url, model_id, region_name. */
  embedding?: Record<string, string>;
  match?: CheckMatch | null;
  tool?: string | null;
  tool_name?: string | null;
  /** tool_called: more tools, any of which counts; only_tools: the tools that may be used, or with Should not, may not. */
  tools?: CheckToolRef[];
  agent?: string | null;
  agent_name?: string | null;
  args?: Record<string, string>;
  succeeds?: boolean;
  result_not_empty?: boolean;
  result_contains?: string | null;
  min_calls?: number | null;
  max_calls?: number | null;
  step?: string | null;
  step_name?: string | null;
  /** Any step of this node type, when no one step is picked. */
  step_type?: string | null;
  router?: string | null;
  router_name?: string | null;
  branch?: string | null;
  branch_label?: string | null;
  key?: string | null;
  /** value_equals: where in the turn the value is, as a dotted path. */
  path?: string | null;
  value?: string | null;
}

// The older methods an evaluation had before they became checks, and what could not become one.
export interface OlderMethods {
  techniques?: string[];
  technique_configs?: Record<string, unknown>;
  left_out?: string[];
  /** Saved in the editor since, so the note has been seen. */
  reviewed?: boolean;
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

