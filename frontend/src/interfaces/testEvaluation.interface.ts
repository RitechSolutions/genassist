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

