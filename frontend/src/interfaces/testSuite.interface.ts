import type { TestToolRuleResult } from "./testEvaluation.interface";


export interface TestSuite {
  id?: string;
  name: string;
  description?: string;
  /** A team's own label, shared with evaluations; null when none is set. */
  category?: string | null;
  workflow_id?: string;
  default_input_metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface TestCase {
  id?: string;
  suite_id: string;
  input_data: Record<string, unknown>;
  expected_output?: Record<string, unknown>;
  tags?: string[];
  weight?: number;
  /** Cases sharing a source conversation replay as one memory thread. */
  source_conversation_id?: string | null;
  /** Position of this turn within its source conversation. */
  turn_index?: number | null;
  created_at?: string;
  updated_at?: string;
}

/** Outcome of one conversation inside a multi-conversation import. */
export interface ImportedConversationResult {
  conversation_id: string;
  status: "imported" | "replaced" | "failed";
  turns: number;
  /** Why it failed, in one sentence. Only set on a failure. */
  detail?: string | null;
}

/** Response of `POST /cases/import-from-conversations`. */
export interface ImportFromConversationsResult {
  /** Every turn created by this import, across all conversations. */
  cases: TestCase[];
  /** One entry per requested conversation, in the order they were requested. */
  results: ImportedConversationResult[];
  imported: number;
  replaced: number;
  failed: number;
}

/** One uploaded file of a dataset file import, and what it adds. */
export interface DatasetFileResult {
  filename: string;
  /** evaluation_bundle files belong to the evaluation import instead. */
  status: "ok" | "failed" | "evaluation_bundle";
  /** What the file adds, after skipping conversations seen before. */
  conversations: number;
  turns: number;
  /** Skipped because the dataset already holds them. */
  duplicates: number;
  /** Skipped because an earlier file in this import, or this one, already has them. */
  repeated: number;
  /** Positions in `files` of the files holding the first copies. */
  repeated_from: number[];
  /** Why the file cannot be imported. */
  errors: string[];
}

/** Response of `POST /cases/import-from-files` and of its preview. */
export interface ImportCasesFromFilesResult {
  /** One entry per uploaded file, in upload order. */
  files: DatasetFileResult[];
  conversations: number;
  turns: number;
  duplicates: number;
  repeated: number;
  failed_files: number;
  /** Set when the import cannot go ahead at all, e.g. it adds too many turns. */
  error?: string | null;
}

/** One dataset, and what it already holds of a given conversation. */
export interface ConversationDataset {
  suite_id: string;
  name: string;
  description?: string | null;
  /** Turns of this conversation already in the dataset. 0 means not in it yet. */
  turns: number;
  /** When the conversation first joined this dataset, or null if it has not. */
  added_at?: string | null;
}

/** Outcome of one dataset inside an add-to-datasets call. */
export interface ConversationDatasetResult {
  suite_id: string;
  status: "imported" | "replaced" | "failed";
  turns: number;
  /** Why it failed, in one sentence. Only set on a failure. */
  detail?: string | null;
}

/** Response of `POST /conversations/{id}/suites`. */
export interface AddConversationToDatasetsResult {
  /** One entry per requested dataset, in the order they were requested. */
  results: ConversationDatasetResult[];
  imported: number;
  replaced: number;
  failed: number;
}

export interface RunProgress {
  conversations_done: number;
  conversations_total: number;
  turns_done: number;
  turns_total: number;
}

export interface TestRun {
  id?: string;
  suite_id: string;
  workflow_id: string;
  status: string;
  techniques: string[];
  summary_metrics?: Record<string, unknown>;
  /** Null until the run starts; updated after each turn. */
  progress?: RunProgress | null;
  workflow_name?: string | null;
  workflow_version?: string | null;
  created_at?: string;
  updated_at?: string;
  /** Its place among the evaluation's runs, 1 for the first; set by the page, not the API. */
  number?: number;
}

export interface MetricRuleDetail {
  rule_number?: number;
  passed: boolean;
  comment?: string | null;
  expected?: string | null;
  observed?: string | null;
}

export interface TestResultMetric {
  score: number | boolean | null;
  passed: boolean;
  error?: boolean;
  not_evaluated?: boolean;
  comment?: string | null;
  expected?: string | null;
  actual?: string | null;
  threshold?: number | null;
  details?: MetricRuleDetail[] | null;
}

export interface TestResult {
  id?: string;
  run_id: string;
  case_id: string;
  actual_output?: Record<string, unknown>;
  execution_trace?: Record<string, unknown>;
  metrics?: Record<string, TestResultMetric>;
  error?: string | null;
  /** scored | execution_failed | scoring_failed | skipped; null for legacy results. */
  status?: string | null;
  created_at?: string;
  updated_at?: string;
}

export type Verdict = "passed" | "failed" | "not_evaluated";

/** How many of a run's conversations passed, failed or were not evaluated. */
export interface ConversationCounts {
  total: number;
  passed: number;
  failed: number;
  not_evaluated: number;
}

/** One turn of a run, as its results page shows it. */
export interface RunTurnResult {
  case_id: string;
  /** Position in its conversation, from 1. */
  number: number;
  /** What the run sent. */
  message: string;
  expected?: string | null;
  reply?: string | null;
  verdict: Verdict;
  /** Why the turn crashed or was not evaluated. */
  reason?: string | null;
  status?: string | null;
  metrics: Record<string, TestResultMetric>;
  rules: TestToolRuleResult[];
  has_trace: boolean;
  /** False when the turn was removed from the dataset after the run. */
  in_dataset: boolean;
}

export interface RunConversationResult {
  key: string;
  verdict: Verdict;
  turns: RunTurnResult[];
  /** Checks on the whole conversation. */
  rules: TestToolRuleResult[];
}

export interface RunConversations {
  run_id: string;
  counts: ConversationCounts;
  /** In the order the run played them. */
  conversations: RunConversationResult[];
  /** Checks whose conversation is not in the run. */
  other_rules: TestToolRuleResult[];
  /** Checks and rules are graded when the run ends, and it has not completed. */
  rules_pending?: boolean;
}

export interface CreateTestSuitePayload {
  name: string;
  description?: string;
  /** On an update, "" clears it. */
  category?: string;
  workflow_id?: string;
  default_input_metadata?: Record<string, unknown>;
}

export interface CreateTestCasePayload {
  input_data: Record<string, unknown>;
  /** Explicit null clears the stored value; undefined leaves it untouched. */
  expected_output?: Record<string, unknown> | null;
  tags?: string[];
  weight?: number;
  /** Cases sharing this replay as one memory thread. */
  source_conversation_id?: string | null;
  turn_index?: number | null;
}
