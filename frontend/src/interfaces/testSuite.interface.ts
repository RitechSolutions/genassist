import type { Workflow } from "@/interfaces/workflow.interface";

export interface TestSuite {
  id?: string;
  name: string;
  description?: string;
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

export interface TestRun {
  id?: string;
  suite_id: string;
  workflow_id: string;
  status: string;
  techniques: string[];
  summary_metrics?: Record<string, unknown>;
  workflow_name?: string | null;
  workflow_version?: string | null;
  created_at?: string;
  updated_at?: string;
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

export interface CreateTestSuitePayload {
  name: string;
  description?: string;
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
