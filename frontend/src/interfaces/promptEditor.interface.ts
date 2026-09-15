import type { TestResultMetric } from "@/interfaces/testSuite.interface";

export interface PromptVersion {
  id: string;
  workflow_id: string;
  node_id: string;
  prompt_field: string;
  version_number: number;
  content: string;
  label: string | null;
  created_at: string;
  created_by: string | null;
}

export interface PromptConfig {
  id: string | null;
  workflow_id: string;
  node_id: string;
  prompt_field: string;
  gold_suite_id: string | null;
  created_at: string | null;
}

/** Versions saved under a shared DOM id before nodes carried their own history */
export interface LegacyPromptHistory {
  node_id: string;
  versions: PromptVersion[];
  gold_suite_id: string | null;
}

export interface PromptHistory {
  versions: PromptVersion[];
  gold_suite_id: string | null;
  node_type: string | null;
  node_missing: boolean;
  field_label: string | null;
  inline_check_supported: boolean;
  unsupported_reason: string | null;
  legacy_shared: LegacyPromptHistory | null;
}

/** Why a case has no verdict, mirroring ResultStatus vocabulary */
export type PromptCaseStatus =
  | "scored"
  | "execution_failed"
  | "scoring_failed"
  | "skipped";

export type PromptCaseVerdict = "passed" | "failed" | "inconclusive";
export type PromptEvalMetric = TestResultMetric & { not_applicable?: boolean };

export interface PromptEvalCaseResult {
  case_id: string;
  input: string;
  expected: string;
  actual: string;
  actual_truncated: boolean;
  status: PromptCaseStatus;
  error: string | null;
  metrics: Record<string, PromptEvalMetric>;
  verdict: PromptCaseVerdict | null;
  passed: boolean;
  case_score: number | null;
  scored_metrics: number;
  failed_metrics: number;
  errored_metrics: number;
  not_evaluated_metrics: number;
  not_applicable_metrics: number;
}

export interface PromptEvalSummary {
  total: number;
  passed: number;
  failed: number;
  inconclusive: number;
  execution_failed: number;
  scoring_failed: number;
  skipped: number;
  scored: number;
  avg_score: number | null;
}

/** What the run actually did, so the header can state it rather than imply it */
export interface PromptRunProvenance {
  mode: "isolated_prompt";
  provider_id: string;
  /** "" when the provider row has no model provider set */
  provider_key: string;
  model: string;
  techniques: string[];
  evaluated_case_ids: string[];
  total_cases: number;
  trials: number;
  ran_at: string;
  latency_ms_total: number;
  usage_total: Record<string, number>;
  budget_seconds: number;
  deadline_hit: boolean;
  metering_handoff_failed: boolean;
}

export interface PromptEvalResponse {
  results: PromptEvalCaseResult[];
  summary: PromptEvalSummary;
  provenance: PromptRunProvenance;
}

export interface PromptOptimizeResponse {
  suggested_prompt: string;
  explanation: string;
  exposure: Record<string, string[]>;
  examples_truncated: boolean;
  holdout_case_ids: string[];
  exploratory: boolean;
  provenance: PromptRunProvenance;
}

export interface CreatePromptVersionPayload {
  content: string;
  label?: string;
}

export interface GoldSuiteLinkPayload {
  suite_id?: string;
  name?: string;
}

/** Options for the techniques that take them. nli_eval gets a fixed evidence
 *  source server-side; llm_judge and provenance_eval are rejected outright */
export interface PromptTechniqueConfigs {
  not_contains?: { phrases: string[] };
  field_equals?: { field: string; expected?: string };
}

export interface PromptEvalRequestPayload {
  prompt_content: string;
  techniques: string[];
  provider_id: string;
  technique_configs?: PromptTechniqueConfigs;
  case_ids?: string[];
  max_cases?: number;
}

export interface PromptOptimizeRequestPayload {
  provider_id: string;
  current_prompt: string;
  instructions?: string;
  failed_cases?: Array<{
    case_id: string;
    actual: string;
    failed_metrics: string[];
  }>;
  case_split?: { holdout_case_ids: string[] };
  techniques?: string[];
}
