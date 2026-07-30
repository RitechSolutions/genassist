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

export interface TestRun {
  id?: string;
  suite_id: string;
  workflow_id: string;
  status: string;
  techniques: string[];
  summary_metrics?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
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
  expected_output?: Record<string, unknown>;
  tags?: string[];
  weight?: number;
}

export interface StartTestRunPayload {
  techniques: string[];
  technique_configs?: Record<string, Record<string, unknown>>;
  workflow_id?: string;
  input_metadata?: Record<string, unknown>;
}
