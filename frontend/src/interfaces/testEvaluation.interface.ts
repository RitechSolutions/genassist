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

