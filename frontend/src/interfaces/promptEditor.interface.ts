export interface PromptVersion {
  id: string;
  workflow_id: string;
  node_id: string;
  prompt_field: string;
  version_number: number;
  content: string;
  label: string | null;
  is_active: boolean;
  created_at: string;
  created_by: string | null;
}

export interface PromptConfig {
  id: string;
  workflow_id: string;
  node_id: string;
  prompt_field: string;
  gold_suite_id: string | null;
  created_at: string;
}

export interface PromptEvalCaseResult {
  case_id: string;
  input: string;
  expected: string;
  actual: string;
  metrics: Record<string, { score: number | boolean; passed: boolean; comment?: string }>;
  passed: boolean;
}

export interface PromptEvalSummary {
  total: number;
  passed: number;
  avg_score: number;
}

export interface PromptEvalResponse {
  results: PromptEvalCaseResult[];
  summary: PromptEvalSummary;
}

export interface PromptOptimizeResponse {
  suggested_prompt: string;
  explanation: string;
}

export interface CreatePromptVersionPayload {
  content: string;
  label?: string;
}

export interface GoldSuiteLinkPayload {
  suite_id?: string;
  name?: string;
}

export interface PromptEvalRequestPayload {
  prompt_content: string;
  techniques: string[];
  provider_id: string;
}

export interface PromptOptimizeRequestPayload {
  provider_id: string;
  current_prompt: string;
  instructions?: string;
  failed_cases?: Array<{ input: string; expected: string; actual: string }>;
}
